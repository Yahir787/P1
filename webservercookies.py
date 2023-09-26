from functools import cached_property
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qsl, urlparse
import re
import redis
import uuid 
from urllib import parse

r = redis.Redis(host='localhost', port=6379, db=0)

class WebRequestHandler(BaseHTTPRequestHandler):
    @cached_property
    def url(self):
        return urlparse(self.path)

    @cached_property
    def cookies(self):
        return SimpleCookie(self.headers.get("Cookie"))
    
    @cached_property
    def query_data(self):
        return dict(parse_qsl(self.url.query))

    def set_book_cookie(self, session_id, max_age=10):
        c = SimpleCookie()
        c["session"] = session_id
        c["session"]["max-age"] = max_age
        self.send_header('Set-Cookie', c.output(header=''))

    def get_book_session(self):
        c = self.cookies
        if not c:
            print("No cookie")
            c = SimpleCookie()
            c["session"] = uuid.uuid4()
        else:
            print("Cookie found")
        return c.get("session").value

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()

        books = None

        if self.query_data and 'q' in self.query_data:
            query = self.query_data['q']
            book_ids = r.sinter(query.split(' '))
            if book_ids:
                book_id_list = list(book_ids)
                if book_id_list:
                    # Obtén la URL del libro desde Redis
                    book_url = r.get(book_id_list[0])
                    if book_url:
                        self.send_response(302)
                        self.send_header('Location', book_url.decode())
                        self.end_headers()
                        return

        self.wfile.write(self.get_response(books).encode("utf-8"))
        
        method = self.get_method(self.url.path)
        if method:
            method_name, dict_params = method
            method = getattr(self, method_name)
            method(**dict_params)
            return
        else:
            self.send_error(404, "Not Found")
       
        
   


    def get_response(self, books): #aca
        return f"""
    <a href= "/"><h1> GoodReads </h1></a>
    <form action="/" method="get">
        <label for="q"> Busqueda </label>
        <input type="text" name="q" required />
    </form>
"""

    def get_book_recomendation(self, session_id, book_id):
        r.rpush(session_id, book_id)
        books = r.lrange(session_id, 0, 5)  # Obtén todos los libros visitados
        if len(books) >= 1:
            all_books = [str(i+1) for i in range(5)] 
            visited_books = [vb.decode() for vb in books]
            unvisited_books = [b for b in all_books if b not in visited_books]
            if unvisited_books:
                return unvisited_books[0]
        return None  # No hay suficientes libros visitados para proporcionar una recomendación


    #def register_book_visit(self, session_id, book_id):
        # Obtiene la lista actual de libros visitados del usuario
     #   visited_books = r.lrange(session_id, 0, -1)
    
        # Verifica si el libro ya se ha visitado
      #  if book_id.encode() not in visited_books:
            # Si el libro no se ha visitado previamente, agrégalo a la lista de visitas
       #     r.rpush(session_id, book_id)

    def get_book(self, book_id):
        session_id = self.get_book_session()
        
        # Llama a la función para registrar la visita al libro
        #self.register_book_visit(session_id, book_id)
        
        book_recomendation = self.get_book_recomendation(session_id, book_id)
        book_page = r.get(book_id)
        if book_page:
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.set_book_cookie(session_id)
            self.end_headers()
            response = f"""
            {book_page.decode()}
            <p>  Ruta: {self.path}            </p>
            <p>  URL: {self.url}              </p>
            <p>  HEADERS: {self.headers}      </p>
            <p>  SESSION: {session_id}      </p>
            """
            if book_recomendation:
                response += f"<p>  Recomendación: <a href='/books/{book_recomendation}'>Libro {book_recomendation}</a></p>"

            self.wfile.write(response.encode("utf-8"))
        else:
            self.send_error(404, "Not Found")


    

    def get_index(self):
        session_id = self.get_book_session()
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.set_book_cookie(session_id)
        self.end_headers()
        with open('html/index.html') as f:
            response = f.read()
        self.wfile.write(response.encode("utf-8"))

    def get_method(self, path):
        for pattern, method in mapping:
            match = re.match(pattern, path)
            if match:
                return (method, match.groupdict())
    
    




mapping = [
            (r'^/books/(?P<book_id>\d+)$', 'get_book'),
            (r'^/$', 'get_index')
        ]

if __name__ == "__main__":
    print("Server starting...")
    server = HTTPServer(("0.0.0.0", 8000), WebRequestHandler)
    server.serve_forever()

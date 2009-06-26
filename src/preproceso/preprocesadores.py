#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
Funciones para generar los ránkings de las páginas.
Todas reciben como argumento una WikiPagina.

Más tarde otra funcion se encargará del algoritmo que produce el
ordenamiento final de las páginas, tomando estos subtotales como
referencia.

(facundobatista) Cambié la interacción entre los procesadores y quien
los llama: ahora los procesadores NO tocan el 'resultado' del WikiSitio,
ya que esto hacía que se pierda el control del mismo y aparezcan páginas
espúeras al final.  Ahora cada procesador devuelve dos cosas: el puntaje
de la página que procesa, y una lista de tuplas (otra_página, puntaje) en
caso de asignar puntajes a otras páginas.  En caso de querer omitir la
página que se le ofrece, el procesador debe devolver None en lugar del
puntaje.

"""
from re import compile, MULTILINE, DOTALL
from urllib2 import unquote
import codecs

from src import utiles
import config

# Procesadores:
class Procesador(object):
    """
    Procesador Genérico, no usar directamente

    """
    def __init__(self, wikisitio):
        """
        Instancia el procesador con los datos necesarios.

        """
        self.valor_inicial = ''
        self.nombre = 'Procesador Genérico'
        self.log = None # ej.: open("archivo.log", "w")

    def __call__(self, wikiarchivo):
        """
        Aplica el procesador a una instancia de WikiArchivo.

        """
        # Ejemplo:
        # return (123456, [])
        raise NotImplemented


class Namespaces(Procesador):
    """
    Se registra el namespace de la página al mismo tiempo que
    se descartan las páginas de namespaces declarados inválidos.

    """
    def __init__(self, wikisitio):
        super(Namespaces, self).__init__(wikisitio)
        self.nombre = "Namespaces"
        self.log = codecs.open(config.LOG_OMITIDO, "w", "utf-8")


    def __call__(self, wikiarchivo):
        (namespace, restonom) = utiles.separaNombre(wikiarchivo.url)

#        print 'Namespace:', repr(namespace) or '(Principal)',
        # no da puntaje per se, pero invalida segun namespace
        if namespace in config.NAMESPACES_INVALIDOS:
#            print '[inválido]'
            self.log.write(wikiarchivo.url + "\n")
            return (None, [])
        else:
#            print '[válido]'
            return (0, [])


class OmitirRedirects(Procesador):
    """
    Procesa y omite de la compilación a los redirects

    """
    def __init__(self, wikisitio):
        super(OmitirRedirects, self).__init__(wikisitio)
        self.nombre = "Redirects-"
        self.log = codecs.open(config.LOG_REDIRECTS, "w", "utf-8")
        regex = r'<meta http-equiv="Refresh" content="\d*;?url=.*?([^/">]+)"'
        self.capturar = compile(regex).search

    def __call__(self, wikiarchivo):
        captura = self.capturar(wikiarchivo.html)

        # no da puntaje per se, pero invalida segun namespace
        sep_col = config.SEPARADOR_COLUMNAS
        if captura:
            url_redirect = unquote(captura.groups()[0]).decode("utf-8")
#            print "Redirect ->", url_redirect.encode("latin1","replace")
            linea = wikiarchivo.url + sep_col + url_redirect + "\n"
            self.log.write(linea)
            return (None, [])
        else:
            return (0, [])


class ExtraerContenido(Procesador):
    """
    Extrae el contenido principal del html de un artículo

    """
    def __init__(self, wikisitio):
        super(ExtraerContenido, self).__init__(wikisitio)
        self.nombre = "Contenido"
        self.valor_inicial = 0
        regex = '(<h1 class="firstHeading">.+</h1>).*<!-- start content -->\s*(.+)\s*<!-- end content -->'
        self.capturar = compile(regex, MULTILINE|DOTALL).search

    def __call__(self, wikiarchivo):
        # Sólo procesamos html
        if wikiarchivo.url.endswith('.html'):
            html = wikiarchivo.html
            encontrado = self.capturar(html)
            if not encontrado:
                # Si estamos acá, el html tiene un formato diferente.
                # Por el momento queremos que se sepa.
                raise ValueError, "El archivo %s posee un formato desconocido" % wikiarchivo.url

#            print "Articulo -",
            wikiarchivo.html = "\n".join(encontrado.groups())
            tamanio = len(wikiarchivo.html)
#            print "Tamaño original: %s, Tamaño actual: %s" % (len(html), tamanio)

            # damos puntaje en función del tamaño del contenido
            return (tamanio, [])


class Peishranc(Procesador):
    """
    Registra las veces que una página es referida por las demás páginas.
    Ignora las auto-referencias y los duplicados

    """
    def __init__(self, wikisitio):
        super(Peishranc, self).__init__(wikisitio)
        self.nombre = "Peishranc"
        self.valor_inicial = 0
        regex = r'<a\s+[^>]*?href="\.\.\/.*?([^/>"]+\.html)"'
        self.capturar = compile(regex).findall

    def __call__(self, wikiarchivo):
        enlaces = self.capturar(wikiarchivo.html)
        if not enlaces:
            return (0, [])
        enlaces = set(unquote(x).decode("utf-8") for x in enlaces)

        # sacamos el "auto-bombo"
        if wikiarchivo.url in enlaces:
            enlaces.remove(wikiarchivo.url)

        # no damos puntaje a la página recibida, sino a todos sus apuntados
        puntajes = [(x, 1) for x in enlaces]
        return (0, puntajes)

class Longitud(Procesador):
    """
    Califica las páginas según la longitud del contenido (html).
    Actualmente es innecesario si se usa ExtraerContenido, pero es
    hipotéticamente útil si otros (futuros) procesadores alteraran
    el html de forma significativa.

    """
    def __init__(self, wikisitio):
        super(Longitud, self).__init__(wikisitio)
        self.nombre = "Longitud"
        self.valor_inicial = 0

    def __call__(self, wikiarchivo):
        largo = len(wikiarchivo.html)
#        print "-- Tamaño útil: %d --\n" % largo
        return (largo, [])


# Clases que serán utilizadas para el preprocesamiento
# de cada una de las páginas, en orden de ejecución.
TODOS = [
    Namespaces,
    OmitirRedirects,
    ExtraerContenido,
    Peishranc,
    #Longitud, # No hace más falta, ExtraerContenido lo hace "gratis"
]
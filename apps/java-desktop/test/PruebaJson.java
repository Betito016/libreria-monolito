import library.java.Config;
import library.java.Json;

import java.util.List;
import java.util.Map;

/**
 * Pruebas sin red del lector JSON y de la configuración, con respuestas reales del gateway.
 *   java -cp build test\PruebaJson.java
 */
public class PruebaJson {
    static int fallas = 0;

    static void verificar(boolean condicion, String nombre) {
        System.out.println((condicion ? "OK    " : "FALLA ") + nombre);
        if (!condicion) fallas++;
    }

    public static void main(String[] args) {
        String salud = "{\"estado\": \"degraded\", \"gateway\": \"library-api-gateway\", \"servicios\": {\"books\": {\"instancias\": ["
                + "{\"url\": \"http://127.0.0.1:5001\", \"estado\": \"down\", \"error\": \"ConnectionRefusedError\", \"ms\": 1},"
                + "{\"url\": \"http://127.0.0.1:6001\", \"http\": 200, \"detalle\": \"ok\", \"estado\": \"ok\", \"ms\": 9}], \"estado\": \"degraded\"}}}";
        Object s = Json.parse(salud);
        verificar("degraded".equals(Json.ruta(s, "estado")), "salud: estado global");
        verificar("degraded".equals(Json.ruta(s, "servicios", "books", "estado")), "salud: estado de books");
        verificar(((List<?>) Json.ruta(s, "servicios", "books", "instancias")).size() == 2, "salud: 2 instancias de books");

        String libros = "{\"filtros\":{},\"libros\":[{\"anio\":1949,\"autores\":[\"Mat\\u00edas Ortega\"],\"isbn\":\"9780451524935\","
                + "\"precio\":430.0,\"stock\":25,\"titulo\":\"1984\",\"categoria\":\"Literatura\"}],\"page\":1,\"total\":30}";
        Map<?, ?> libro = (Map<?, ?>) ((List<?>) Json.ruta(Json.parse(libros), "libros")).get(0);
        verificar("Matías Ortega".equals(Json.texto(libro.get("autores"))), "catálogo: autor con \\u00ed");
        verificar("430".equals(Json.texto(libro.get("precio"))) && "25".equals(Json.texto(libro.get("stock"))), "catálogo: números");

        String error = "{\"estado\":\"error\",\"codigo_error\":\"ERR_SERVICIO_NO_DISPONIBLE\",\"mensaje\":\"El servicio pagos no está disponible en este momento.\",\"request_id\":\"abc\"}";
        verificar(Json.ruta(Json.parse(error), "mensaje").toString().startsWith("El servicio pagos"), "error 503 del gateway");
        verificar(Json.ruta(Json.parse("{\"ok\":true,\"n\":null,\"l\":[]}"), "ok") == Boolean.TRUE, "literales true/null/[]");

        String cuerpo = Json.objeto(new java.util.LinkedHashMap<>(Map.of("email", "a\"b@x.test")));
        verificar(cuerpo.equals("{\"email\":\"a\\\"b@x.test\"}"), "escritura JSON con comillas");

        verificar("http://34.135.84.31:8080".equals(Config.normalizar("34.135.84.31:8080/")), "config: normalizar");
        verificar(Config.validar("http://34.135.84.31") == null, "config: gateway válido");
        verificar(Config.validar("http://34.135.84.31/api/books") != null, "config: rechaza rutas");
        verificar(Config.validar("ftp://x") != null, "config: rechaza otro esquema");

        System.out.println(fallas == 0 ? "\nTODAS LAS PRUEBAS PASARON" : "\n" + fallas + " PRUEBA(S) FALLARON");
        System.exit(fallas == 0 ? 0 : 1);
    }
}

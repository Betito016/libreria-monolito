package library.java;

import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.LocalTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.function.Consumer;

/**
 * Único lugar de la app que usa la red. TODAS las peticiones van al Library API Gateway:
 *
 *   gateway + "/api/<servicio>" + ruta del servicio
 *   http://34.135.84.31/api/books/books?format=json  ->  nginx  ->  books (5001 o 6001)
 *
 * - Agrega "Authorization: Bearer <JWT>" solo en las rutas protegidas (users) y en logout.
 * - Cada petición lleva un X-Request-ID propio; el gateway lo respeta, lo registra y lo devuelve.
 * - El JWT nunca se muestra completo en el registro.
 */
public final class GatewayClient {

    /** Resultado de una petición: código, cuerpo, tiempo y cabeceras útiles del gateway. */
    public record Respuesta(int status, String cuerpo, long ms, String requestId, String instancia, String error) {
        public boolean ok() { return status >= 200 && status < 300; }

        public Object json() {
            try { return Json.parse(cuerpo); } catch (RuntimeException e) { return null; }
        }

        public String mensaje() {
            if (error != null) return error;
            Object datos = json();
            if (datos == null) return "la respuesta no viene del gateway (¿un filtro de red o un proxy en medio?)";
            Object m = Json.ruta(datos, "mensaje");
            return m != null ? m.toString() : "respuesta sin mensaje";
        }
    }

    private static final DateTimeFormatter HORA = DateTimeFormatter.ofPattern("HH:mm:ss");

    private final HttpClient http = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(5))
            .followRedirects(HttpClient.Redirect.NEVER)
            .build();
    private volatile String gateway;
    private volatile String token;
    private final List<String> registro = Collections.synchronizedList(new ArrayList<>());
    private Consumer<String> oyenteRegistro = linea -> { };
    private int contador = 0;

    public GatewayClient(String gateway) { this.gateway = gateway; }

    public String getGateway() { return gateway; }
    public void setGateway(String url) { this.gateway = url; }
    public boolean tieneToken() { return token != null; }
    public void setOyenteRegistro(Consumer<String> oyente) { this.oyenteRegistro = oyente; }

    public static String codificar(String t) { return URLEncoder.encode(t, StandardCharsets.UTF_8); }

    // ------------------------------------------------------------------ operaciones
    /** GET /health del gateway: estado agregado de servicios e instancias. */
    public Respuesta salud() { return enviar("GET", "/health", null, false); }

    /** POST /api/login/login con JSON; guarda el JWT recibido. */
    public Respuesta login(String email, String password) {
        String cuerpo = Json.objeto(new java.util.LinkedHashMap<>(java.util.Map.of("email", email, "password", password)));
        Respuesta r = enviar("POST", "/api/login/login?format=json", cuerpo, false);
        if (r.ok()) {
            Object t = Json.ruta(r.json(), "token", "access_token");
            token = t != null ? t.toString() : null;
        }
        return r;
    }

    /** POST /api/login/logout con Bearer: el servidor revoca el JWT en Redis; la app lo olvida. */
    public Respuesta logout() {
        Respuesta r = enviar("POST", "/api/login/logout?format=json", null, true);
        token = null;
        return r;
    }

    public Respuesta catalogo(String titulo) {
        String filtro = titulo == null || titulo.isBlank() ? "" : "&titulo=" + codificar(titulo.trim());
        return enviar("GET", "/api/books/books?format=json&page_size=100" + filtro, null, false);
    }

    public Respuesta autores() { return enviar("GET", "/api/autores/authors?format=json&page_size=100", null, false); }

    /** Ruta protegida: users exige JWT de administrador (sin token -> 401, rol cliente -> 403). */
    public Respuesta usuarios() { return enviar("GET", "/api/users/users?format=json", null, true); }

    // ------------------------------------------------------------------ HTTP
    private Respuesta enviar(String metodo, String ruta, String json, boolean conToken) {
        String rid = "java-" + Long.toHexString(System.nanoTime()) + "-" + (++contador);
        String url = gateway + ruta;
        HttpRequest.Builder b = HttpRequest.newBuilder(URI.create(url))
                .timeout(Duration.ofSeconds(15))
                .header("Accept", "application/json")
                .header("X-Request-ID", rid);
        boolean llevaToken = conToken && token != null;
        if (llevaToken) b.header("Authorization", "Bearer " + token);
        if (json != null) b.header("Content-Type", "application/json").method(metodo, HttpRequest.BodyPublishers.ofString(json));
        else b.method(metodo, HttpRequest.BodyPublishers.noBody());

        long inicio = System.nanoTime();
        Respuesta r;
        try {
            HttpResponse<String> resp = http.send(b.build(), HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
            long ms = (System.nanoTime() - inicio) / 1_000_000;
            r = new Respuesta(resp.statusCode(), resp.body(), ms,
                    resp.headers().firstValue("X-Request-ID").orElse(rid),
                    resp.headers().firstValue("X-Gateway-Instancia").orElse("-"), null);
        } catch (java.io.IOException e) {
            long ms = (System.nanoTime() - inicio) / 1_000_000;
            r = new Respuesta(0, "", ms, rid, "-", "Sin respuesta del gateway (" + e.getClass().getSimpleName() + ")");
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            r = new Respuesta(0, "", 0, rid, "-", "Interrumpida");
        }
        String rutaSinQuery = ruta.split("\\?")[0];
        String linea = String.format("%s  %-6s %-34s -> HTTP %s  %4d ms  instancia=%-15s rid=%s  %s",
                LocalTime.now().format(HORA), metodo, rutaSinQuery, r.status == 0 ? "---" : r.status, r.ms,
                r.instancia, r.requestId, llevaToken ? "Bearer [JWT PRESENTE]" : "(sin JWT)");
        registro.add(linea);
        System.out.println(linea);
        oyenteRegistro.accept(linea);
        return r;
    }
}

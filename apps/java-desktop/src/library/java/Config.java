package library.java;

import java.io.IOException;
import java.io.Reader;
import java.io.Writer;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Properties;

/**
 * Configuración de la app: SOLO la dirección del Library API Gateway.
 * Se guarda fuera del código, en %APPDATA%\LibreriaJavaApp\config.properties
 * (o ~/.libreria_java_app en otros sistemas). No guarda contraseñas ni tokens.
 *
 * Las rutas de cada servicio se arman a partir de esa dirección:
 *   http://34.135.84.31  +  /api/books/books   ->  servicio books
 */
public final class Config {

    public static final String GATEWAY_PREDETERMINADO = "http://34.135.84.31";

    private static Path archivo() {
        String appdata = System.getenv("APPDATA");
        Path dir = appdata != null ? Path.of(appdata, "LibreriaJavaApp") : Path.of(System.getProperty("user.home"), ".libreria_java_app");
        return dir.resolve("config.properties");
    }

    public static String cargarGateway() {
        Path f = archivo();
        if (Files.exists(f)) {
            Properties p = new Properties();
            try (Reader r = Files.newBufferedReader(f, StandardCharsets.UTF_8)) {
                p.load(r);
                String url = normalizar(p.getProperty("gateway", ""));
                if (validar(url) == null) return url;
            } catch (IOException ignorada) {
                // archivo dañado: se usa el valor por defecto
            }
        }
        return GATEWAY_PREDETERMINADO;
    }

    public static void guardarGateway(String url) throws IOException {
        Path f = archivo();
        Files.createDirectories(f.getParent());
        Properties p = new Properties();
        p.setProperty("gateway", url);
        try (Writer w = Files.newBufferedWriter(f, StandardCharsets.UTF_8)) {
            p.store(w, "Library - app Java: direccion del API Gateway");
        }
    }

    public static String ruta() { return archivo().toString(); }

    /** "34.135.84.31:8080/" -> "http://34.135.84.31:8080" */
    public static String normalizar(String url) {
        url = url == null ? "" : url.trim();
        if (!url.isEmpty() && !url.contains("://")) url = "http://" + url;
        while (url.endsWith("/")) url = url.substring(0, url.length() - 1);
        return url;
    }

    /** null si es válida; si no, el motivo. */
    public static String validar(String url) {
        try {
            URI u = URI.create(url);
            if (!"http".equals(u.getScheme()) && !"https".equals(u.getScheme())) return "Debe empezar con http:// o https://";
            if (u.getHost() == null) return "Falta el servidor (p. ej. 34.135.84.31)";
            if (u.getPath() != null && !u.getPath().isEmpty()) return "Escribe solo la dirección del gateway, sin rutas";
            return null;
        } catch (IllegalArgumentException e) {
            return "Dirección inválida";
        }
    }
}

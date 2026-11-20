package library.java;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Lector y escritor JSON mínimo (sin dependencias externas).
 * Convierte el texto en Map (objeto), List (arreglo), String, Double, Boolean o null.
 * Suficiente para las respuestas de los microservicios de Library.
 */
public final class Json {

    private final String s;
    private int i;

    private Json(String s) { this.s = s; }

    public static Object parse(String texto) {
        Json p = new Json(texto);
        p.espacios();
        Object valor = p.valor();
        p.espacios();
        if (p.i != p.s.length()) throw new IllegalArgumentException("JSON con datos de más en la posición " + p.i);
        return valor;
    }

    /** Serializa un mapa sencillo de texto a JSON (para los cuerpos de las peticiones). */
    public static String objeto(Map<String, String> campos) {
        StringBuilder sb = new StringBuilder("{");
        for (Map.Entry<String, String> e : campos.entrySet()) {
            if (sb.length() > 1) sb.append(',');
            sb.append(cadena(e.getKey())).append(':').append(cadena(e.getValue()));
        }
        return sb.append('}').toString();
    }

    private static String cadena(String t) {
        StringBuilder sb = new StringBuilder("\"");
        for (char c : t.toCharArray()) {
            switch (c) {
                case '"' -> sb.append("\\\"");
                case '\\' -> sb.append("\\\\");
                case '\n' -> sb.append("\\n");
                case '\r' -> sb.append("\\r");
                case '\t' -> sb.append("\\t");
                default -> {
                    if (c < 0x20) sb.append(String.format("\\u%04x", (int) c));
                    else sb.append(c);
                }
            }
        }
        return sb.append('"').toString();
    }

    // ---- Acceso cómodo a datos anidados: Json.ruta(datos, "token", "access_token") ----
    @SuppressWarnings("unchecked")
    public static Object ruta(Object datos, String... claves) {
        Object actual = datos;
        for (String clave : claves) {
            if (!(actual instanceof Map)) return null;
            actual = ((Map<String, Object>) actual).get(clave);
        }
        return actual;
    }

    public static String texto(Object valor) {
        if (valor == null) return "";
        if (valor instanceof Double d && d == Math.rint(d) && !Double.isInfinite(d)) return String.valueOf(d.longValue());
        if (valor instanceof List<?> lista) {
            List<String> partes = new ArrayList<>();
            for (Object o : lista) partes.add(texto(o));
            return String.join(", ", partes);
        }
        return String.valueOf(valor);
    }

    // ---- Analizador recursivo ----
    private Object valor() {
        if (i >= s.length()) throw error("fin inesperado");
        char c = s.charAt(i);
        return switch (c) {
            case '{' -> objeto();
            case '[' -> arreglo();
            case '"' -> cadena();
            case 't' -> literal("true", Boolean.TRUE);
            case 'f' -> literal("false", Boolean.FALSE);
            case 'n' -> literal("null", null);
            default -> numero();
        };
    }

    private Map<String, Object> objeto() {
        Map<String, Object> m = new LinkedHashMap<>();
        i++;
        espacios();
        if (s.charAt(i) == '}') { i++; return m; }
        while (true) {
            espacios();
            String clave = cadena();
            espacios();
            esperar(':');
            espacios();
            m.put(clave, valor());
            espacios();
            if (s.charAt(i) == ',') { i++; continue; }
            esperar('}');
            return m;
        }
    }

    private List<Object> arreglo() {
        List<Object> l = new ArrayList<>();
        i++;
        espacios();
        if (s.charAt(i) == ']') { i++; return l; }
        while (true) {
            espacios();
            l.add(valor());
            espacios();
            if (s.charAt(i) == ',') { i++; continue; }
            esperar(']');
            return l;
        }
    }

    private String cadena() {
        esperar('"');
        StringBuilder sb = new StringBuilder();
        while (true) {
            char c = s.charAt(i++);
            if (c == '"') return sb.toString();
            if (c != '\\') { sb.append(c); continue; }
            char e = s.charAt(i++);
            switch (e) {
                case 'n' -> sb.append('\n');
                case 't' -> sb.append('\t');
                case 'r' -> sb.append('\r');
                case 'b' -> sb.append('\b');
                case 'f' -> sb.append('\f');
                case 'u' -> { sb.append((char) Integer.parseInt(s.substring(i, i + 4), 16)); i += 4; }
                default -> sb.append(e);          // \" \\ \/
            }
        }
    }

    private Double numero() {
        int inicio = i;
        while (i < s.length() && "+-0123456789.eE".indexOf(s.charAt(i)) >= 0) i++;
        if (inicio == i) throw error("carácter inesperado '" + s.charAt(i) + "'");
        return Double.valueOf(s.substring(inicio, i));
    }

    private Object literal(String palabra, Object valor) {
        if (!s.startsWith(palabra, i)) throw error("se esperaba " + palabra);
        i += palabra.length();
        return valor;
    }

    private void esperar(char c) {
        if (i >= s.length() || s.charAt(i) != c) throw error("se esperaba '" + c + "'");
        i++;
    }

    private void espacios() {
        while (i < s.length() && Character.isWhitespace(s.charAt(i))) i++;
    }

    private IllegalArgumentException error(String msg) {
        return new IllegalArgumentException("JSON inválido (posición " + i + "): " + msg);
    }
}

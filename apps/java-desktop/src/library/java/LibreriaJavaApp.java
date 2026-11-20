package library.java;

import java.awt.BorderLayout;
import java.awt.Color;
import java.awt.Dimension;
import java.awt.FlowLayout;
import java.awt.Font;
import java.awt.Graphics;
import java.awt.Graphics2D;
import java.awt.RenderingHints;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.function.Function;
import java.util.function.Supplier;
import javax.swing.BorderFactory;
import javax.swing.JButton;
import javax.swing.JComponent;
import javax.swing.JFrame;
import javax.swing.JLabel;
import javax.swing.JOptionPane;
import javax.swing.JPanel;
import javax.swing.JPasswordField;
import javax.swing.JScrollPane;
import javax.swing.JTabbedPane;
import javax.swing.JTable;
import javax.swing.JTextArea;
import javax.swing.JTextField;
import javax.swing.SwingUtilities;
import javax.swing.SwingWorker;
import javax.swing.Timer;
import javax.swing.UIManager;
import javax.swing.table.DefaultTableModel;

/**
 * Librería en Línea — cliente de escritorio en Java (Swing) del Library API Gateway.
 *
 * La app NO conoce los puertos de los microservicios: solo la dirección del gateway
 * (por defecto http://34.135.84.31). Todo pasa por nginx:
 *
 *   Semáforos      GET  /health                      salud agregada (servicios e instancias)
 *   Iniciar sesión POST /api/login/login              JWT de 20 min
 *   Cerrar sesión  POST /api/login/logout            revoca el JWT en Redis
 *   Catálogo       GET  /api/books/books              público; balanceado entre :5001 y :6001
 *   Autores        GET  /api/autores/authors          público
 *   Usuarios       GET  /api/users/users              protegido: Bearer de administrador
 *
 * La red se usa siempre en segundo plano (SwingWorker): la ventana nunca se congela.
 */
public final class LibreriaJavaApp extends JFrame {

    private static final String[] SERVICIOS = {"login", "books", "users", "autores", "pedidos", "pagos", "soap"};
    private static final Color VERDE = new Color(0x16A34A), AMARILLO = new Color(0xEAB308), ROJO = new Color(0xDC2626),
            GRIS = new Color(0x9CA3AF), BARRA = new Color(0x1E293B);

    private final GatewayClient cliente = new GatewayClient(Config.cargarGateway());
    private final Map<String, Semaforo> luces = new LinkedHashMap<>();
    private final JLabel estadoGateway = etiquetaClara("Gateway: sin comprobar");
    private final JTextField campoGateway = new JTextField(cliente.getGateway(), 22);
    private final JTextField campoEmail = new JTextField("admin@libreria.test", 16);
    private final JPasswordField campoPassword = new JPasswordField(12);
    private final JLabel estadoSesion = etiquetaClara("Sin sesión");
    private final JButton botonLogin = new JButton("Iniciar sesión");
    private final JLabel barraEstado = new JLabel(" ");
    private final JTextArea registro = new JTextArea();

    private final DefaultTableModel modeloLibros = modelo("ISBN", "Título", "Autor(es)", "Categoría", "Precio", "Stock");
    private final DefaultTableModel modeloAutores = modelo("ID", "Nombre", "Nacionalidad", "Libros");
    private final DefaultTableModel modeloUsuarios = modelo("Correo", "Nombre", "Rol", "Activo", "Verificado");
    private final JTextField campoBusqueda = new JTextField(18);

    public LibreriaJavaApp() {
        super("Librería en Línea · Cliente Java del API Gateway");
        setDefaultCloseOperation(EXIT_ON_CLOSE);
        setSize(1180, 720);
        setLocationRelativeTo(null);
        setLayout(new BorderLayout());
        add(barraSuperior(), BorderLayout.NORTH);
        add(pestanas(), BorderLayout.CENTER);
        barraEstado.setBorder(BorderFactory.createEmptyBorder(4, 10, 4, 10));
        add(barraEstado, BorderLayout.SOUTH);

        cliente.setOyenteRegistro(linea -> SwingUtilities.invokeLater(() -> {
            registro.append(linea + "\n");
            registro.setCaretPosition(registro.getDocument().getLength());
        }));
        // Semáforos: GET /health ahora y cada 15 s.
        comprobarSalud();
        new Timer(15_000, e -> comprobarSalud()).start();
        cargarCatalogo();
        cargarAutores();
    }

    // ================================================================== interfaz
    private JComponent barraSuperior() {
        JPanel norte = new JPanel(new BorderLayout());
        norte.setBackground(BARRA);

        JPanel fila1 = new JPanel(new FlowLayout(FlowLayout.LEFT, 10, 8));
        fila1.setOpaque(false);
        JLabel titulo = etiquetaClara("📚 Librería en Línea · Java");
        titulo.setFont(titulo.getFont().deriveFont(Font.BOLD, 16f));
        fila1.add(titulo);
        for (String s : SERVICIOS) {
            Semaforo luz = new Semaforo();
            luces.put(s, luz);
            fila1.add(luz);
            fila1.add(etiquetaClara(s));
        }
        fila1.add(estadoGateway);

        JPanel fila2 = new JPanel(new FlowLayout(FlowLayout.LEFT, 8, 6));
        fila2.setOpaque(false);
        fila2.add(etiquetaClara("API Gateway:"));
        fila2.add(campoGateway);
        JButton guardar = new JButton("Guardar y probar");
        guardar.addActionListener(e -> guardarGateway());
        fila2.add(guardar);
        fila2.add(etiquetaClara("   Correo:"));
        fila2.add(campoEmail);
        fila2.add(etiquetaClara("Contraseña:"));
        fila2.add(campoPassword);
        botonLogin.addActionListener(e -> alternarSesion());
        campoPassword.addActionListener(e -> alternarSesion());
        fila2.add(botonLogin);
        fila2.add(estadoSesion);

        norte.add(fila1, BorderLayout.NORTH);
        norte.add(fila2, BorderLayout.SOUTH);
        return norte;
    }

    private JComponent pestanas() {
        JTabbedPane tabs = new JTabbedPane();

        JPanel catalogo = new JPanel(new BorderLayout());
        JPanel buscar = new JPanel(new FlowLayout(FlowLayout.LEFT));
        buscar.add(new JLabel("Buscar por título:"));
        buscar.add(campoBusqueda);
        JButton botonBuscar = new JButton("Buscar");
        botonBuscar.addActionListener(e -> cargarCatalogo());
        campoBusqueda.addActionListener(e -> cargarCatalogo());
        buscar.add(botonBuscar);
        buscar.add(new JLabel("   GET /api/books/books · público · balanceado entre 2 instancias (ver Registro HTTP)"));
        catalogo.add(buscar, BorderLayout.NORTH);
        catalogo.add(new JScrollPane(tabla(modeloLibros)), BorderLayout.CENTER);
        tabs.addTab("Catálogo", catalogo);

        tabs.addTab("Autores", panelConRecarga("GET /api/autores/authors · público", modeloAutores, this::cargarAutores));
        tabs.addTab("Usuarios (admin)", panelConRecarga(
                "GET /api/users/users · requiere JWT de administrador (sin sesión → 401)", modeloUsuarios, this::cargarUsuarios));

        registro.setEditable(false);
        registro.setFont(new Font(Font.MONOSPACED, Font.PLAIN, 12));
        registro.setBackground(new Color(0x0F172A));
        registro.setForeground(new Color(0xE2E8F0));
        JPanel panelRegistro = new JPanel(new BorderLayout());
        panelRegistro.add(new JLabel("  Cada petición: método, ruta en el gateway, código, tiempo, instancia que atendió y X-Request-ID"),
                BorderLayout.NORTH);
        panelRegistro.add(new JScrollPane(registro), BorderLayout.CENTER);
        tabs.addTab("Registro HTTP", panelRegistro);
        return tabs;
    }

    private JComponent panelConRecarga(String descripcion, DefaultTableModel modelo, Runnable accion) {
        JPanel p = new JPanel(new BorderLayout());
        JPanel arriba = new JPanel(new FlowLayout(FlowLayout.LEFT));
        JButton recargar = new JButton("↻ Actualizar");
        recargar.addActionListener(e -> accion.run());
        arriba.add(recargar);
        arriba.add(new JLabel("  " + descripcion));
        p.add(arriba, BorderLayout.NORTH);
        p.add(new JScrollPane(tabla(modelo)), BorderLayout.CENTER);
        return p;
    }

    // ================================================================== acciones
    private void guardarGateway() {
        String url = Config.normalizar(campoGateway.getText());
        String error = Config.validar(url);
        if (error != null) {
            JOptionPane.showMessageDialog(this, error, "Dirección del gateway", JOptionPane.WARNING_MESSAGE);
            return;
        }
        try {
            Config.guardarGateway(url);
        } catch (java.io.IOException e) {
            estado("No se pudo guardar la configuración: " + e.getMessage(), true);
        }
        campoGateway.setText(url);
        cliente.setGateway(url);
        estado("Gateway guardado en " + Config.ruta() + ". Probando GET /health…", false);
        comprobarSalud();
        cargarCatalogo();
        cargarAutores();
    }

    private void comprobarSalud() {
        enSegundoPlano(cliente::salud, r -> {
            Object servicios = Json.ruta(r.json(), "servicios");
            for (Map.Entry<String, Semaforo> e : luces.entrySet()) {
                Object estado = Json.ruta(servicios, e.getKey(), "estado");
                e.getValue().fijar(estado == null ? GRIS : switch (estado.toString()) {
                    case "ok" -> VERDE;
                    case "degraded" -> AMARILLO;
                    default -> ROJO;
                });
                Object instancias = Json.ruta(servicios, e.getKey(), "instancias");
                e.getValue().setToolTipText(e.getKey() + ": " + estado + (instancias instanceof List<?> l ? " · " + l.size() + " instancia(s)" : ""));
            }
            Object global = Json.ruta(r.json(), "estado");
            estadoGateway.setText("   Gateway: " + (global != null ? global + " (HTTP " + r.status() + ")" : r.mensaje()));
        });
    }

    private void alternarSesion() {
        if (cliente.tieneToken()) {
            enSegundoPlano(cliente::logout, r -> {
                estadoSesion.setText("Sin sesión");
                botonLogin.setText("Iniciar sesión");
                modeloUsuarios.setRowCount(0);
                estado("Sesión cerrada (HTTP " + r.status() + "): el servidor revocó el JWT y la app lo olvidó.", false);
            });
            return;
        }
        String email = campoEmail.getText().trim();
        String password = new String(campoPassword.getPassword());
        if (email.isEmpty() || password.isEmpty()) {
            estado("Escribe correo y contraseña.", true);
            return;
        }
        enSegundoPlano(() -> cliente.login(email, password), r -> {
            campoPassword.setText("");
            if (r.ok()) {
                Object nombre = Json.ruta(r.json(), "usuario", "nombre");
                Object rol = Json.ruta(r.json(), "usuario", "rol");
                estadoSesion.setText(nombre + " · " + rol + " · JWT 20 min");
                botonLogin.setText("Cerrar sesión");
                estado("Sesión iniciada a través del gateway (HTTP " + r.status() + ", " + r.ms() + " ms).", false);
                cargarUsuarios();
            } else {
                estado("No se pudo iniciar sesión: " + r.mensaje() + (r.status() > 0 ? " (HTTP " + r.status() + ")" : ""), true);
            }
        });
    }

    private void cargarCatalogo() {
        String titulo = campoBusqueda.getText();
        llenar(() -> cliente.catalogo(titulo), modeloLibros, "libros", l -> new Object[]{
                Json.texto(l.get("isbn")), Json.texto(l.get("titulo")), Json.texto(l.get("autores")),
                Json.texto(l.get("categoria")), "$" + Json.texto(l.get("precio")), Json.texto(l.get("stock"))});
    }

    private void cargarAutores() {
        llenar(cliente::autores, modeloAutores, "autores", a -> new Object[]{
                Json.texto(a.get("id")), Json.texto(a.get("nombre")), Json.texto(a.get("nacionalidad")),
                Json.texto(a.get("total_libros"))});
    }

    private void cargarUsuarios() {
        llenar(cliente::usuarios, modeloUsuarios, "usuarios", u -> new Object[]{
                Json.texto(u.get("email")), (Json.texto(u.get("nombre")) + " " + Json.texto(u.get("apellido_paterno"))).trim(),
                Json.texto(u.get("rol")), siNo(u.get("activo")), siNo(u.get("email_verificado"))});
    }

    /** Pide la lista en segundo plano y llena la tabla; si falla, muestra el motivo (401, 403, 503…). */
    @SuppressWarnings("unchecked")
    private void llenar(Supplier<GatewayClient.Respuesta> peticion, DefaultTableModel modelo, String clave,
                        Function<Map<String, Object>, Object[]> fila) {
        enSegundoPlano(peticion, r -> {
            modelo.setRowCount(0);
            if (!r.ok()) {
                estado(clave + ": " + r.mensaje() + (r.status() > 0 ? " (HTTP " + r.status() + ")" : ""), true);
                return;
            }
            Object lista = Json.ruta(r.json(), clave);
            if (lista instanceof List<?> elementos) {
                for (Object e : elementos) if (e instanceof Map) modelo.addRow(fila.apply((Map<String, Object>) e));
            }
            estado(String.format("%s: %d registro(s) · HTTP %d en %d ms · atendió %s · X-Request-ID %s",
                    clave, modelo.getRowCount(), r.status(), r.ms(), r.instancia(), r.requestId()), false);
        });
    }

    // ================================================================== utilidades
    private <T> void enSegundoPlano(Supplier<T> trabajo, java.util.function.Consumer<T> alTerminar) {
        new SwingWorker<T, Void>() {
            @Override protected T doInBackground() { return trabajo.get(); }
            @Override protected void done() {
                try { alTerminar.accept(get()); }
                catch (Exception e) { estado("Error inesperado: " + e.getMessage(), true); }
            }
        }.execute();
    }

    private void estado(String texto, boolean error) {
        barraEstado.setText(texto);
        barraEstado.setForeground(error ? ROJO : new Color(0x166534));
    }

    private static String siNo(Object v) { return Boolean.TRUE.equals(v) ? "sí" : "no"; }

    private static JLabel etiquetaClara(String texto) {
        JLabel l = new JLabel(texto);
        l.setForeground(Color.WHITE);
        return l;
    }

    private static DefaultTableModel modelo(String... columnas) {
        return new DefaultTableModel(columnas, 0) {
            @Override public boolean isCellEditable(int fila, int columna) { return false; }
        };
    }

    private static JTable tabla(DefaultTableModel modelo) {
        JTable t = new JTable(modelo);
        t.setRowHeight(24);
        t.setAutoCreateRowSorter(true);
        return t;
    }

    /** Círculo de color para el estado de cada servicio. */
    private static final class Semaforo extends JComponent {
        private Color color = GRIS;
        Semaforo() { setPreferredSize(new Dimension(14, 14)); }
        void fijar(Color c) { color = c; repaint(); }
        @Override protected void paintComponent(Graphics g) {
            Graphics2D g2 = (Graphics2D) g.create();
            g2.setRenderingHint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_ON);
            g2.setColor(color);
            g2.fillOval(1, 1, getWidth() - 2, getHeight() - 2);
            g2.dispose();
        }
    }

    public static void main(String[] args) {
        try { UIManager.setLookAndFeel(UIManager.getSystemLookAndFeelClassName()); } catch (Exception ignorada) { }
        SwingUtilities.invokeLater(() -> new LibreriaJavaApp().setVisible(true));
    }
}

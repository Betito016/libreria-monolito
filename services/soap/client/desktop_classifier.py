import sys
import tkinter as tk
from tkinter import ttk, messagebox
import xml.etree.ElementTree as ET
import requests

SOAP_URL = "http://localhost:5000/soap"
SOAP_ENV_NS = "http://schemas.xmlsoap.org/soap/envelope/"
TNS_NS = "http://udem.edu/iac/library/soap"
WSSE_NS = "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd"

class DesktopClassifierApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("UDEM - Cliente SOAP de Clasificación de Catálogo (2026)")
        self.geometry("950x700")
        self.minsize(850, 600)
        self.configure(bg="#0f172a")

        self.pending_concepts = []
        self._setup_styles()
        self._create_widgets()

    def _setup_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")

        # Configuración de colores oscuros modernos
        style.configure(".", background="#0f172a", foreground="#f8fafc", font=("Segoe UI", 10))
        style.configure("TLabel", background="#0f172a", foreground="#cbd5e1")
        style.configure("Header.TLabel", font=("Segoe UI", 14, "bold"), foreground="#38bdf8")
        style.configure("SubHeader.TLabel", font=("Segoe UI", 11, "bold"), foreground="#94a3b8")
        
        style.configure("TFrame", background="#1e293b")
        style.configure("Card.TFrame", background="#1e293b", relief="flat")
        
        style.configure("TButton", font=("Segoe UI", 10, "bold"), background="#0284c7", foreground="#ffffff", borderwidth=0, padding=6)
        style.map("TButton", background=[("active", "#0369a1")])

        style.configure("Secondary.TButton", font=("Segoe UI", 9), background="#334155", foreground="#ffffff", borderwidth=0, padding=5)
        style.map("Secondary.TButton", background=[("active", "#475569")])

        style.configure("Treeview", 
                        background="#0f172a", 
                        foreground="#f8fafc", 
                        fieldbackground="#0f172a", 
                        font=("Segoe UI", 9),
                        rowheight=26)
        style.configure("Treeview.Heading", 
                        background="#334155", 
                        foreground="#38bdf8", 
                        font=("Segoe UI", 10, "bold"))
        style.map("Treeview", background=[("selected", "#0284c7")])

    def _create_widgets(self):
        # 1. Cabecera principal
        header_frame = tk.Frame(self, bg="#0f172a", pady=10)
        header_frame.pack(fill="x", padx=20)

        title_lbl = ttk.Label(header_frame, text="📚 Clasificador de Catálogo Cloud (Cliente SOAP)", style="Header.TLabel")
        title_lbl.pack(anchor="w")

        sub_lbl = ttk.Label(header_frame, text="Módulo SOAP Flask + psycopg2 | Integración Desacoplada sin tocar Monolito", style="SubHeader.TLabel")
        sub_lbl.pack(anchor="w")

        # 2. Formulario de Datos del Clasificador
        user_card = ttk.Frame(self, style="Card.TFrame", padding=12)
        user_card.pack(fill="x", padx=20, pady=5)

        ttk.Label(user_card, text="👤 Identidad del Clasificador:", style="SubHeader.TLabel").grid(row=0, column=0, columnspan=6, sticky="w", pady=(0, 6))

        ttk.Label(user_card, text="Nombre:").grid(row=1, column=0, sticky="w", padx=4)
        self.ent_nombre = ttk.Entry(user_card, width=15)
        self.ent_nombre.insert(0, "Alex")
        self.ent_nombre.grid(row=1, column=1, sticky="w", padx=4)

        ttk.Label(user_card, text="Apellidos:").grid(row=1, column=2, sticky="w", padx=4)
        self.ent_apellidos = ttk.Entry(user_card, width=15)
        self.ent_apellidos.insert(0, "Morales")
        self.ent_apellidos.grid(row=1, column=3, sticky="w", padx=4)

        ttk.Label(user_card, text="Email:").grid(row=1, column=4, sticky="w", padx=4)
        self.ent_email = ttk.Entry(user_card, width=22)
        self.ent_email.insert(0, "alex.morales@udem.edu")
        self.ent_email.grid(row=1, column=5, sticky="w", padx=4)

        # 3. Contenedor Central: Tabla de Conceptos Pendientes
        table_card = ttk.Frame(self, style="Card.TFrame", padding=12)
        table_card.pack(fill="both", expand=True, padx=20, pady=8)

        btn_row = tk.Frame(table_card, bg="#1e293b")
        btn_row.pack(fill="x", pady=(0, 6))

        ttk.Label(btn_row, text="📋 Conceptos Pendientes en Catálogo:", style="SubHeader.TLabel").pack(side="left")
        
        btn_fetch = ttk.Button(btn_row, text="🔄 Consultar Pendientes (SOAP)", command=self.fetch_pending_concepts)
        btn_fetch.pack(side="right", padx=4)

        btn_prog = ttk.Button(btn_row, text="📊 Ver Mi Progreso", style="Secondary.TButton", command=self.check_user_progress)
        btn_prog.pack(side="right", padx=4)

        # Tabla Treeview
        columns = ("id", "nombre", "libro", "categoria", "isbn")
        self.tree = ttk.Treeview(table_card, columns=columns, show="headings", height=7)
        self.tree.heading("id", text="ID")
        self.tree.heading("nombre", text="Concepto")
        self.tree.heading("libro", text="Libro Asociado")
        self.tree.heading("categoria", text="Categoría")
        self.tree.heading("isbn", text="ISBN")

        self.tree.column("id", width=45, anchor="center")
        self.tree.column("nombre", width=90, anchor="center")
        self.tree.column("libro", width=340)
        self.tree.column("categoria", width=110, anchor="center")
        self.tree.column("isbn", width=140, anchor="center")

        self.tree.pack(fill="both", expand=True, side="left")
        self.tree.bind("<<TreeviewSelect>>", self._on_concept_selected)

        tree_scroll = ttk.Scrollbar(table_card, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)
        tree_scroll.pack(side="right", fill="y")

        # 4. Panel de Detalle y Clasificación
        action_card = ttk.Frame(self, style="Card.TFrame", padding=12)
        action_card.pack(fill="x", padx=20, pady=5)

        ttk.Label(action_card, text="🏷️ Asignar Clasificación de Servicio Cloud:", style="SubHeader.TLabel").pack(anchor="w", pady=(0, 4))

        # Definición del concepto seleccionado
        self.lbl_def = tk.Label(action_card, text="Selecciona un concepto de la tabla superior para ver su definición completa.",
                                bg="#0f172a", fg="#94a3b8", font=("Segoe UI", 9, "italic"), wraplength=880, justify="left", padx=8, pady=6)
        self.lbl_def.pack(fill="x", pady=4)

        ctrl_row = tk.Frame(action_card, bg="#1e293b")
        ctrl_row.pack(fill="x", pady=6)

        ttk.Label(ctrl_row, text="Modelo Cloud:").pack(side="left", padx=(0, 8))
        self.cb_model = ttk.Combobox(ctrl_row, values=["IaaS", "PaaS", "SaaS", "FaaS"], state="readonly", width=10)
        self.cb_model.current(0)
        self.cb_model.pack(side="left", padx=4)

        btn_classify = ttk.Button(ctrl_row, text="🚀 Enviar Clasificación (SOAP POST)", command=self.send_classification)
        btn_classify.pack(side="left", padx=15)

        btn_stats = ttk.Button(ctrl_row, text="🔐 Estadísticas Globales (WS-Security)", style="Secondary.TButton", command=self.open_stats_modal)
        btn_stats.pack(side="right", padx=4)

        # 5. Barra de Estado Inferior
        self.status_bar = tk.Label(self, text="Listo | Endpoint: http://localhost:5000/soap", bd=1, relief="sunken", anchor="w",
                                   bg="#0284c7", fg="#ffffff", font=("Segoe UI", 9))
        self.status_bar.pack(side="bottom", fill="x")

    def _on_concept_selected(self, event):
        selected_item = self.tree.selection()
        if not selected_item:
            return
        item_vals = self.tree.item(selected_item[0], "values")
        c_id = int(item_vals[0])

        for c in self.pending_concepts:
            if c['id'] == c_id:
                self.lbl_def.config(
                    text=f"📖 Definición: {c['definition']}\n(Libro: {c['book_title']} | ISBN: {c['isbn']})",
                    fg="#f8fafc"
                )
                break

    def fetch_pending_concepts(self):
        """Construye sobre SOAP y consulta la lista de conceptos pendientes."""
        email = self.ent_email.get().strip()
        soap_req = f"""<?xml version="1.0" encoding="UTF-8"?>
        <soapenv:Envelope xmlns:soapenv="{SOAP_ENV_NS}" xmlns:tns="{TNS_NS}">
            <soapenv:Header/>
            <soapenv:Body>
                <tns:ObtenerConceptosPendientesRequest>
                    <tns:clasificador_email>{email}</tns:clasificador_email>
                </tns:ObtenerConceptosPendientesRequest>
            </soapenv:Body>
        </soapenv:Envelope>"""

        try:
            resp = requests.post(SOAP_URL, data=soap_req.encode('utf-8'), headers={'Content-Type': 'text/xml; charset=utf-8'}, timeout=5)
            if resp.status_code == 200:
                self._parse_and_fill_tree(resp.text)
                self.status_bar.config(text=f"Conceptos cargados exitosamente desde SOAP ({len(self.pending_concepts)} encontrados).")
            else:
                self._handle_soap_fault(resp.text, resp.status_code)
        except Exception as e:
            messagebox.showerror("Error de Conexión", f"No fue posible conectar con el servidor SOAP:\n{e}")

    def _parse_and_fill_tree(self, xml_text: str):
        for row in self.tree.get_children():
            self.tree.delete(row)
        self.pending_concepts.clear()

        root = ET.fromstring(xml_text)
        # Buscar nodos de conceptos
        for c_elem in root.iter(f"{{{TNS_NS}}}conceptos"):
            cid = c_elem.find(f"{{{TNS_NS}}}concepto_id").text
            cnom = c_elem.find(f"{{{TNS_NS}}}concepto_nombre").text
            cdef = c_elem.find(f"{{{TNS_NS}}}definicion").text
            cisbn = c_elem.find(f"{{{TNS_NS}}}libro_isbn").text
            ctit = c_elem.find(f"{{{TNS_NS}}}libro_titulo").text
            ccat = c_elem.find(f"{{{TNS_NS}}}categoria").text

            self.pending_concepts.append({
                'id': int(cid),
                'name': cnom,
                'definition': cdef,
                'isbn': cisbn,
                'book_title': ctit,
                'category': ccat
            })
            self.tree.insert("", "end", values=(cid, cnom, ctit, ccat, cisbn))

    def send_classification(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Atención", "Por favor selecciona un concepto de la tabla primero.")
            return

        item_vals = self.tree.item(selected[0], "values")
        c_id = item_vals[0]
        c_isbn = item_vals[4]
        c_name = item_vals[1]

        nombre = self.ent_nombre.get().strip()
        apellidos = self.ent_apellidos.get().strip()
        email = self.ent_email.get().strip()
        modelo = self.cb_model.get().strip()

        if not nombre or not apellidos or not email:
            messagebox.showwarning("Campos Requeridos", "Por favor completa los datos de tu identidad (Nombre, Apellidos y Email).")
            return

        soap_req = f"""<?xml version="1.0" encoding="UTF-8"?>
        <soapenv:Envelope xmlns:soapenv="{SOAP_ENV_NS}" xmlns:tns="{TNS_NS}">
            <soapenv:Header/>
            <soapenv:Body>
                <tns:RegistrarClasificacionRequest>
                    <tns:nombre>{nombre}</tns:nombre>
                    <tns:apellidos>{apellidos}</tns:apellidos>
                    <tns:email>{email}</tns:email>
                    <tns:concepto_id>{c_id}</tns:concepto_id>
                    <tns:libro_isbn>{c_isbn}</tns:libro_isbn>
                    <tns:modelo_cloud>{modelo}</tns:modelo_cloud>
                    <tns:cliente_tipo>Desktop-Tkinter-GUI</tns:cliente_tipo>
                    <tns:cliente_id>GUI-USER-01</tns:cliente_id>
                </tns:RegistrarClasificacionRequest>
            </soapenv:Body>
        </soapenv:Envelope>"""

        try:
            resp = requests.post(SOAP_URL, data=soap_req.encode('utf-8'), headers={'Content-Type': 'text/xml; charset=utf-8'}, timeout=5)
            if resp.status_code == 200:
                root = ET.fromstring(resp.text)
                msg = root.find(f".//{{{TNS_NS}}}mensaje").text
                cid = root.find(f".//{{{TNS_NS}}}clasificacion_id").text
                messagebox.showinfo("Clasificación Exitosa", f"✅ {msg}\nID Transacción: {cid}")
                self.status_bar.config(text=f"Clasificación registrada con éxito para concepto {c_id}.")
                self.fetch_pending_concepts()
            else:
                self._handle_soap_fault(resp.text, resp.status_code)
        except Exception as e:
            messagebox.showerror("Error", f"Error al comunicar con SOAP:\n{e}")

    def check_user_progress(self):
        email = self.ent_email.get().strip()
        if not email:
            messagebox.showwarning("Email Requerido", "Ingresa tu email para consultar tu progreso.")
            return

        soap_req = f"""<?xml version="1.0" encoding="UTF-8"?>
        <soapenv:Envelope xmlns:soapenv="{SOAP_ENV_NS}" xmlns:tns="{TNS_NS}">
            <soapenv:Header/>
            <soapenv:Body>
                <tns:ObtenerProgresoUsuarioRequest>
                    <tns:email>{email}</tns:email>
                </tns:ObtenerProgresoUsuarioRequest>
            </soapenv:Body>
        </soapenv:Envelope>"""

        try:
            resp = requests.post(SOAP_URL, data=soap_req.encode('utf-8'), headers={'Content-Type': 'text/xml; charset=utf-8'}, timeout=5)
            if resp.status_code == 200:
                root = ET.fromstring(resp.text)
                nombre = root.find(f".//{{{TNS_NS}}}nombre_completo").text
                clasif = root.find(f".//{{{TNS_NS}}}total_clasificados").text
                pend = root.find(f".//{{{TNS_NS}}}total_pendientes").text
                pct = root.find(f".//{{{TNS_NS}}}porcentaje_progreso").text

                messagebox.showinfo("Progreso del Clasificador", 
                                    f"👤 Clasificador: {nombre}\n"
                                    f"📧 Email: {email}\n\n"
                                    f"✅ Clasificados: {clasif}\n"
                                    f"⏳ Pendientes: {pend}\n"
                                    f"📈 Progreso: {pct}%")
            else:
                self._handle_soap_fault(resp.text, resp.status_code)
        except Exception as e:
            messagebox.showerror("Error", f"No fue posible consultar el progreso:\n{e}")

    def open_stats_modal(self):
        """Abre ventana modal para consultar estadísticas protegidas por WS-Security."""
        modal = tk.Toplevel(self)
        modal.title("🔐 Estadísticas por Modelo (WS-Security)")
        modal.geometry("450x380")
        modal.configure(bg="#1e293b")
        modal.transient(self)
        modal.grab_set()

        tk.Label(modal, text="Autenticación WS-Security Requerida", font=("Segoe UI", 11, "bold"), bg="#1e293b", fg="#38bdf8").pack(pady=10)
        tk.Label(modal, text="Operación protegida para auditar métricas globales del catálogo.", font=("Segoe UI", 8), bg="#1e293b", fg="#94a3b8").pack()

        form = tk.Frame(modal, bg="#1e293b")
        form.pack(pady=10)

        tk.Label(form, text="Usuario WS-Security:", bg="#1e293b", fg="#cbd5e1").grid(row=0, column=0, sticky="w", pady=4)
        ent_u = ttk.Entry(form, width=20)
        ent_u.insert(0, "admin_clasificador")
        ent_u.grid(row=0, column=1, pady=4)

        tk.Label(form, text="Password WS-Security:", bg="#1e293b", fg="#cbd5e1").grid(row=1, column=0, sticky="w", pady=4)
        ent_p = ttk.Entry(form, width=20, show="*")
        ent_p.insert(0, "CloudSecure2026!")
        ent_p.grid(row=1, column=1, pady=4)

        res_box = tk.Label(modal, text="Presione 'Consultar' para enviar solicitud autenticada.", bg="#0f172a", fg="#94a3b8", font=("Consolas", 9), justify="left", padx=10, pady=10, relief="groove")
        res_box.pack(fill="x", padx=20, pady=10)

        def do_auth_query():
            user = ent_u.get().strip()
            password = ent_p.get().strip()

            soap_req = f"""<?xml version="1.0" encoding="UTF-8"?>
            <soapenv:Envelope xmlns:soapenv="{SOAP_ENV_NS}" 
                              xmlns:tns="{TNS_NS}"
                              xmlns:wsse="{WSSE_NS}">
                <soapenv:Header>
                    <wsse:Security>
                        <wsse:UsernameToken>
                            <wsse:Username>{user}</wsse:Username>
                            <wsse:Password>{password}</wsse:Password>
                        </wsse:UsernameToken>
                    </wsse:Security>
                </soapenv:Header>
                <soapenv:Body>
                    <tns:ObtenerEstadisticasPorModeloRequest/>
                </soapenv:Body>
            </soapenv:Envelope>"""

            try:
                resp = requests.post(SOAP_URL, data=soap_req.encode('utf-8'), headers={'Content-Type': 'text/xml; charset=utf-8'}, timeout=5)
                if resp.status_code == 200:
                    root = ET.fromstring(resp.text)
                    iaas = root.find(f".//{{{TNS_NS}}}total_iaas").text
                    paas = root.find(f".//{{{TNS_NS}}}total_paas").text
                    saas = root.find(f".//{{{TNS_NS}}}total_saas").text
                    faas = root.find(f".//{{{TNS_NS}}}total_faas").text
                    tot = root.find(f".//{{{TNS_NS}}}total_general").text

                    res_box.config(
                        text=f"📊 MÉTRICAS GLOBALES CLOUD:\n"
                             f" • IaaS (Infraestructura): {iaas}\n"
                             f" • PaaS (Plataforma):      {paas}\n"
                             f" • SaaS (Software):        {saas}\n"
                             f" • FaaS (Serverless):      {faas}\n"
                             f" ----------------------------\n"
                             f" TOTAL CLASIFICACIONES:   {tot}",
                        fg="#38bdf8"
                    )
                else:
                    fault_root = ET.fromstring(resp.text)
                    err_msg = fault_root.find(".//faultstring").text if fault_root.find(".//faultstring") is not None else "Error"
                    res_box.config(text=f"❌ SOAP FAULT ({resp.status_code}):\n{err_msg}", fg="#f87171")
            except Exception as ex:
                res_box.config(text=f"❌ Error de red: {ex}", fg="#f87171")

        ttk.Button(modal, text="🔑 Consultar Estadísticas Autenticadas", command=do_auth_query).pack(pady=6)

    def _handle_soap_fault(self, fault_xml: str, http_code: int):
        """Maneja amigablemente la falla SOAP Fault recibida."""
        try:
            root = ET.fromstring(fault_xml)
            faultstring = root.find(".//faultstring")
            fs_text = faultstring.text if faultstring is not None else "Error SOAP"

            detail_msg = root.find(f".//{{{TNS_NS}}}mensaje")
            det_text = detail_msg.text if detail_msg is not None else ""

            code_err = root.find(f".//{{{TNS_NS}}}codigo_error")
            code_text = code_err.text if code_err is not None else f"HTTP {http_code}"

            if http_code == 409 or "409" in code_text:
                messagebox.showwarning("⚠️ Conflicto (SOAP Fault 409)", f"Clasificación Duplicada:\n{det_text or fs_text}")
            elif http_code == 401 or "UNAUTHORIZED" in code_text:
                messagebox.showerror("⛔ No Autorizado (WS-Security)", f"Falla de Autenticación:\n{det_text or fs_text}")
            else:
                messagebox.showerror(f"Error SOAP ({code_text})", f"{fs_text}\n\nDetalle: {det_text}")
        except Exception:
            messagebox.showerror("Error SOAP", f"Falla en el servicio SOAP (HTTP {http_code}):\n{fault_xml}")

if __name__ == "__main__":
    app = DesktopClassifierApp()
    app.mainloop()

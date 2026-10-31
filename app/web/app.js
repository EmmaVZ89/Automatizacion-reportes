// Reportes de cierre: interfaz. Una sola página, sin dependencias. Todo el contenido se construye con nodos del
// DOM (nunca innerHTML), así lo que viene de los archivos no puede ejecutar nada.
'use strict';
(() => {
  const MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];
  const ESTADO_TEXTO = { borrador: 'Sin correr', listo: 'Lista para correr', corriendo: 'Corriendo', esperando: 'Espera una acción tuya', ok: 'Terminado', error: 'Con error', cancelado: 'Cancelado' };
  const ICONOS_REPORTE = { balanza: 'i-balanza', lista: 'i-lista', reloj: 'i-mora', cheque: 'i-cheque', factura: 'i-factura', reporte: 'i-reporte' };
  const PASOS = [
    { nombre: 'Archivos', icono: 'i-subir', ayuda: 'archivos' },
    { nombre: 'Opciones', icono: 'i-ajustes', ayuda: 'opciones' },
    { nombre: 'Ejecución', icono: 'i-play', ayuda: 'ejecucion' },
    { nombre: 'Resultados', icono: 'i-tabla', ayuda: 'resultados' },
    { nombre: 'Exportar', icono: 'i-bajar', ayuda: 'exportar' },
  ];
  const estado = { app: null, conf: null, vista: null, w: null, fuente: null, sondeo: null, sello: 0, cargas: 0 };
  const SVG = 'http://www.w3.org/2000/svg';

  // ---------------------------------------------------------------- utilidades
  const $ = (sel, raiz = document) => raiz.querySelector(sel);
  const nuevoSello = () => ++estado.sello;
  const vigente = s => s === estado.sello;

  function el(tag, attrs, ...hijos) {
    const n = document.createElement(tag);
    if (attrs) {
      for (const [k, v] of Object.entries(attrs)) {
        if (v === null || v === undefined || v === false) continue;
        if (k === 'class') n.className = v;
        else if (k === 'text') n.textContent = v;
        else if (k.startsWith('on')) n.addEventListener(k.slice(2), v);
        else if (k === 'checked' || k === 'disabled' || k === 'selected' || k === 'open' || k === 'multiple') n[k] = !!v;
        else if (k === 'value') n.value = v;
        else if (k === 'style') n.style.cssText = v;
        else n.setAttribute(k, v === true ? '' : v);
      }
    }
    for (const h of hijos.flat()) {
      if (h === null || h === undefined || h === false) continue;
      n.appendChild(typeof h === 'string' || typeof h === 'number' ? document.createTextNode(String(h)) : h);
    }
    return n;
  }
  function svg(tag, attrs, ...hijos) {
    const n = document.createElementNS(SVG, tag);
    for (const [k, v] of Object.entries(attrs || {})) n.setAttribute(k, v);
    for (const h of hijos.flat()) if (h) n.appendChild(h);
    return n;
  }
  const icono = (nombre, clase = '') => svg('svg', { class: ('i ' + clase).trim(), 'aria-hidden': 'true' }, svg('use', { href: '#' + nombre }));
  const limpiar = n => { while (n.firstChild) n.removeChild(n.firstChild); return n; };
  function btn(texto, onclick, clase = '', opciones = {}) {
    const b = el('button', { type: 'button', class: 'btn ' + clase, onclick, title: opciones.title, disabled: opciones.disabled, 'aria-label': opciones.aria });
    if (opciones.icono) b.appendChild(icono(opciones.icono));
    if (texto) b.appendChild(el('span', null, texto));
    return b;
  }
  const enlace = (texto, href, clase = 'btn', iconoNombre = null) => el('a', { href, class: clase }, iconoNombre ? icono(iconoNombre) : null, el('span', null, texto));
  const tileReporte = (r, clase = '') => el('span', { class: `tile ${r.codigo} ${clase}`.trim() }, icono(ICONOS_REPORTE[r.icono] || 'i-reporte'));

  function periodoLargo(p) {
    const m = /^(\d{4})-(\d{2})$/.exec(p || '');
    if (!m) return p || '';
    const mes = MESES[parseInt(m[2], 10) - 1] || m[2];
    return mes.charAt(0).toUpperCase() + mes.slice(1) + ' ' + m[1];
  }
  function fechaCorta(iso) {
    const m = /^(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}):(\d{2}))?/.exec(iso || '');
    if (!m) return iso || '';
    return `${m[3]}/${m[2]}/${m[1]}` + (m[4] ? ` ${m[4]}:${m[5]}` : '');
  }
  function fechaLarga(iso) {
    const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || '');
    if (!m) return iso || '';
    return `${parseInt(m[3], 10)} de ${MESES[parseInt(m[2], 10) - 1]} de ${m[1]}`;
  }
  const n = v => Number(v || 0).toLocaleString('es-AR');
  const bytesLegibles = b => b >= 1048576 ? (b / 1048576).toFixed(1).replace('.', ',') + ' MB' : b >= 1024 ? Math.round(b / 1024) + ' KB' : b + ' bytes';
  const hoy = () => new Date();
  const hoyIso = () => { const d = hoy(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`; };
  const finDeMes = p => { const m = /^(\d{4})-(\d{2})$/.exec(p || ''); if (!m) return ''; const d = new Date(parseInt(m[1], 10), parseInt(m[2], 10), 0); return `${m[1]}-${m[2]}-${String(d.getDate()).padStart(2, '0')}`; };
  const periodoDe = d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
  function numeroLegible(v) {
    const m = /^(-?)(\d+)[.,](\d{1,4})$/.exec(v || '');
    if (!m) return v;
    const entero = Number(m[2]).toLocaleString('es-AR');
    return `${m[1]}${entero},${m[3]}`;
  }

  // ---------------------------------------------------------------- servidor
  function progresoGlobal(delta) {
    estado.cargas = Math.max(0, estado.cargas + delta);
    $('#progreso-global').classList.toggle('activo', estado.cargas > 0);
  }
  async function api(metodo, ruta, cuerpo, opciones = {}) {
    const init = { method: metodo, credentials: 'same-origin', headers: {} };
    if (opciones.crudo) { init.body = cuerpo; Object.assign(init.headers, opciones.cabeceras || {}); }
    else if (cuerpo !== undefined) { init.headers['Content-Type'] = 'application/json'; init.body = JSON.stringify(cuerpo); }
    let mostrada = false;
    const lento = setTimeout(() => { mostrada = true; progresoGlobal(1); }, 250);
    let r;
    try {
      r = await fetch(ruta, init);
    } catch (e) {
      throw new Error('No se pudo hablar con la herramienta. Si la cerraste, volvé a abrirla desde su acceso directo.');
    } finally {
      clearTimeout(lento);
      if (mostrada) progresoGlobal(-1);
    }
    const tipo = r.headers.get('Content-Type') || '';
    const datos = tipo.includes('json') ? await r.json() : await r.text();
    if (!r.ok) { const e = new Error((datos && datos.error) || `Error ${r.status}`); e.status = r.status; throw e; }
    return datos;
  }

  // ---------------------------------------------------------------- avisos
  const ICONO_AVISO = { ok: 'i-check', error: 'i-x', atencion: 'i-alerta', info: 'i-info' };
  function aviso(texto, tipo = 'info', ms = 5500) {
    const caja = el('div', { class: 'aviso ' + tipo, role: tipo === 'error' ? 'alert' : 'status' },
      el('span', { class: 'icono' }, icono(ICONO_AVISO[tipo] || 'i-info')),
      el('div', { class: 'texto' }, texto),
      el('button', { type: 'button', class: 'cerrar', 'aria-label': 'Cerrar aviso', onclick: () => quitar() }, icono('i-x')),
      el('span', { class: 'tiempo', style: `animation-duration:${ms}ms` }));
    const quitar = () => { if (!caja.isConnected) return; caja.classList.add('saliendo'); setTimeout(() => caja.remove(), 250); };
    $('#avisos').appendChild(caja);
    setTimeout(quitar, ms);
  }
  const avisarError = e => aviso(e.message || String(e), 'error', 9000);

  // ---------------------------------------------------------------- diálogos
  const ICONO_TONO = { pregunta: 'i-ayuda', peligro: 'i-alerta', ok: 'i-check', aviso: 'i-alerta', info: 'i-info' };
  function dialogo({ titulo, texto, boton = 'Aceptar', cancelar = 'Cancelar', tono = 'pregunta', campo = null }) {
    return new Promise(resolve => {
      const d = $('#dialogo');
      limpiar(d);
      d.className = 'dialogo ' + tono;
      let entrada = null;
      if (campo) {
        entrada = campo.multilinea ? el('textarea', { 'aria-label': titulo, rows: '4' }) : el('input', { type: campo.tipo || 'text', 'aria-label': titulo });
        entrada.value = campo.valor || '';
      }
      let resuelto = false;
      const cerrar = valor => { if (resuelto) return; resuelto = true; d.close(); resolve(valor); };
      d.append(
        el('div', { class: 'dialogo-cuerpo' },
          el('div', { class: 'dialogo-icono' }, icono(ICONO_TONO[tono] || 'i-info')),
          el('div', { class: 'dialogo-texto' }, el('h2', null, titulo), texto ? el('p', null, texto) : null, entrada ? el('div', { class: 'campo' }, entrada) : null)),
        el('div', { class: 'dialogo-botones' },
          cancelar ? btn(cancelar, () => cerrar(null), 'fantasma') : null,
          btn(boton, () => cerrar(entrada ? entrada.value : true), tono === 'peligro' ? 'peligro' : 'primario')));
      d.addEventListener('cancel', () => cerrar(null), { once: true });
      d.showModal();
      if (entrada) entrada.focus(); else { const b = d.querySelector('.dialogo-botones .btn:last-child'); if (b) b.focus(); }
    });
  }
  const confirmar = (titulo, texto, boton = 'Sí', tono = 'pregunta') => dialogo({ titulo, texto, boton, tono }).then(v => v === true);
  const pedirTexto = (titulo, texto, valor = '', multilinea = false) => dialogo({ titulo, texto, boton: 'Guardar', tono: 'info', campo: { valor, multilinea } });

  function abrirModal({ titulo, iconoNombre = null, tileNodo = null, cuerpo, pie = [], ancho = false, alCerrar = null }) {
    const d = $('#modal');
    limpiar(d);
    d.className = 'modal' + (ancho ? ' ancho' : '');
    const cerrar = () => { if (d.open) d.close(); };
    d.append(
      el('div', { class: 'modal-cabecera' }, tileNodo || (iconoNombre ? el('span', { class: 'tile', style: 'width:38px;height:38px;background:var(--accent-suave);color:var(--accent)' }, icono(iconoNombre)) : null),
        el('h2', null, titulo), el('button', { type: 'button', class: 'btn fantasma icono', 'aria-label': 'Cerrar', onclick: cerrar }, icono('i-x'))),
      el('div', { class: 'modal-cuerpo' }, cuerpo),
      pie.length ? el('div', { class: 'modal-pie' }, pie) : null);
    d.onclose = () => { if (alCerrar) alCerrar(); };
    d.showModal();
    const principal = d.querySelector('.modal-pie .btn.primario');
    if (principal) principal.focus();
    return { d, cerrar };
  }

  // ---------------------------------------------------------------- menús
  let menuAbierto = null;
  function cerrarMenu() {
    if (!menuAbierto) return;
    menuAbierto.menu.remove();
    menuAbierto.ancla.setAttribute('aria-expanded', 'false');
    menuAbierto = null;
  }
  function abrirMenu(ancla, items) {
    const mismo = menuAbierto && menuAbierto.ancla === ancla;
    cerrarMenu();
    if (mismo) return;
    const menu = el('div', { class: 'menu', role: 'menu' });
    for (const it of items) {
      if (it === 'sep') { menu.appendChild(el('div', { class: 'sep' })); continue; }
      if (it.titulo) { menu.appendChild(el('div', { class: 'titulo-menu' }, it.titulo)); continue; }
      menu.appendChild(el('button', { type: 'button', role: 'menuitem', class: it.peligro ? 'peligro' : '', onclick: ev => { ev.stopPropagation(); cerrarMenu(); it.onclick(); } },
        icono(it.icono || 'i-der'), el('span', null, it.texto, it.detalle ? el('span', { class: 'detalle' }, it.detalle) : null)));
    }
    ancla.parentElement.appendChild(menu);
    ancla.setAttribute('aria-expanded', 'true');
    menuAbierto = { menu, ancla };
    const primero = menu.querySelector('button');
    if (primero) primero.focus();
  }
  document.addEventListener('click', ev => { if (menuAbierto && !menuAbierto.menu.contains(ev.target) && !menuAbierto.ancla.contains(ev.target)) cerrarMenu(); });
  document.addEventListener('keydown', ev => {
    if (ev.key === 'Escape') { if (menuAbierto) { const a = menuAbierto.ancla; cerrarMenu(); a.focus(); } else if ($('#cajon').classList.contains('abierto')) cerrarAyuda(); }
  });
  function botonMenu(items, etiqueta = 'Más acciones') {
    const envoltura = el('div', { class: 'menu-envoltura' });
    const b = el('button', { type: 'button', class: 'btn fantasma icono', 'aria-label': etiqueta, title: etiqueta, 'aria-haspopup': 'menu', 'aria-expanded': 'false', onclick: ev => { ev.stopPropagation(); ev.preventDefault(); abrirMenu(b, typeof items === 'function' ? items() : items); } }, icono('i-puntos'));
    envoltura.appendChild(b);
    return envoltura;
  }

  // ---------------------------------------------------------------- confeti
  function fiesta() {
    const lienzo = $('#lienzo-fiesta');
    const ctx = lienzo.getContext('2d');
    const ancho = lienzo.width = window.innerWidth;
    const alto = lienzo.height = window.innerHeight;
    const colores = ['#3445B4', '#FF8A5B', '#18A16B', '#FFD166', '#6D3FC9', '#0B8AC9'];
    const piezas = Array.from({ length: 150 }, () => ({
      x: ancho / 2 + (Math.random() - .5) * ancho * .3, y: alto * .35, vx: (Math.random() - .5) * 15, vy: -Math.random() * 15 - 5,
      r: Math.random() * Math.PI, vr: (Math.random() - .5) * .35, w: 7 + Math.random() * 6, h: 4 + Math.random() * 5, c: colores[Math.floor(Math.random() * colores.length)],
    }));
    const inicio = performance.now();
    const cuadro = t => {
      const dt = Math.min(1, (t - inicio) / 2400);
      ctx.clearRect(0, 0, ancho, alto);
      for (const p of piezas) {
        p.vy += .38; p.vx *= .99; p.x += p.vx; p.y += p.vy; p.r += p.vr;
        ctx.save(); ctx.globalAlpha = 1 - dt; ctx.translate(p.x, p.y); ctx.rotate(p.r); ctx.fillStyle = p.c; ctx.fillRect(-p.w / 2, -p.h / 2, p.w, p.h); ctx.restore();
      }
      if (dt < 1) requestAnimationFrame(cuadro); else ctx.clearRect(0, 0, ancho, alto);
    };
    requestAnimationFrame(cuadro);
  }

  // ---------------------------------------------------------------- tema
  function aplicarTema(t) {
    const tema = t === 'oscuro' ? 'oscuro' : 'claro';
    document.documentElement.dataset.tema = tema;
    const b = $('#btn-tema');
    limpiar(b).appendChild(icono(tema === 'oscuro' ? 'i-sol' : 'i-luna'));
    const texto = tema === 'oscuro' ? 'Cambiar a tema claro' : 'Cambiar a tema oscuro';
    b.title = texto; b.setAttribute('aria-label', texto);
    try { localStorage.setItem('reportes-tema', tema); } catch (e) { /* sin almacenamiento */ }
  }

  // ---------------------------------------------------------------- ayuda
  const AYUDA_PASOS = {
    archivos: { titulo: 'Paso 1: Archivos', icono: 'i-subir', partes: [
      ['p', 'Elegís los Excel que descargaste de los sistemas (SGA y ERP). No hace falta renombrarlos: la herramienta los reconoce por sus columnas.'],
      ['ul', ['Arrastrá los archivos a la zona punteada, o usá "Elegir archivos".', 'Si el archivo ya está en una carpeta de la PC, "Tomar de una carpeta" lo copia sin tocar el original.', 'Si el sistema cortó la descarga en dos o más archivos (pasa cerca de las 454.000 filas), agregá todos: se leen seguidos como uno solo.', 'Un archivo que se usa en varios reportes del mes (como el histórico de SGA) se sube una sola vez y queda disponible para los demás.']],
    ] },
    opciones: { titulo: 'Paso 2: Opciones', icono: 'i-ajustes', partes: [
      ['p', 'Los valores que ves son los que se usan si no tocás nada: casi siempre alcanza con revisar la fecha de corte y las opciones principales.'],
      ['ul', ['Las "opciones avanzadas" son las listas y reglas que antes estaban fijas en los programas. Cambialas sólo si te lo pidieron.', 'Si marcás "Guardar estos valores para los próximos cierres", la próxima vez aparecen ya cargados.']],
    ] },
    ejecucion: { titulo: 'Paso 3: Ejecución', icono: 'i-play', partes: [
      ['p', 'El reporte corre solo. Podés cerrar la pestaña o seguir con otra cosa: sigue corriendo y lo encontrás en el cierre.'],
      ['ul', ['Si necesita algo de vos (por ejemplo iniciar sesión en Chrome), aparece un aviso naranja con el botón para continuar.', 'Si termina con error, el mensaje dice qué pasó. En "Ver el detalle técnico" está lo que hace falta para pedir ayuda.', 'Los reportes grandes tardan entre uno y tres minutos.']],
    ] },
    resultados: { titulo: 'Paso 4: Resultados', icono: 'i-tabla', partes: [
      ['p', 'Cada tabla del reporte se revisa acá adentro, sin abrir Excel.'],
      ['ul', ['Hacé clic en una fila (o en varias) y usá "Revisada" u "Omitir". "Pendiente" deshace la marca.', 'Escribí una observación y guardala para las filas marcadas, o hacé doble clic en la columna Observaciones de una fila.', 'Buscá, filtrá por estado y ordená tocando el título de cada columna.', 'Lo que marques se guarda solo y pasa a la próxima versión del mismo mes. Con "Traer la revisión del cierre anterior" recuperás lo que ya habías omitido el mes pasado.']],
    ] },
    exportar: { titulo: 'Paso 5: Exportar', icono: 'i-bajar', partes: [
      ['p', 'Descargás el Excel "trabajado": el mismo del reporte, con las columnas Estado revisión y Observaciones completas con lo que marcaste.'],
      ['ul', ['También están los archivos originales, tal como los produce el reporte.', 'Marcá la versión como "resultado final del cierre" cuando ya esté revisada: así queda registrada en el historial.']],
    ] },
  };
  const AYUDA_GENERAL = [
    { clave: 'primeros', titulo: 'Cómo es un cierre', icono: 'i-cierre', partes: [
      ['ol', ['Creá el cierre del mes (botón "Nuevo cierre") con su fecha de corte.', 'Entrá a cada reporte del cierre y seguí sus cinco pasos: Archivos, Opciones, Ejecución, Resultados y Exportar.', 'Revisá los resultados: marcá filas como revisadas u omitidas y anotá observaciones.', 'Cuando un reporte quede listo, marcalo como resultado final. Con los cuatro reportes finales, el cierre está completo.']],
      ['p', 'Podés volver a correr un reporte cuantas veces quieras: cada corrida es una versión nueva y lo que ya revisaste pasa solo a la nueva.'],
    ] },
    { clave: 'revision', titulo: 'Revisar los resultados', icono: 'i-check-circulo', partes: [
      ['estados', [['chip borde', 'Pendiente', 'Todavía no la miraste.'], ['chip ok', 'Revisada', 'La miraste y está bien, o ya la resolviste.'], ['chip', 'Omitida', 'No corresponde revisarla este mes (por ejemplo, una diferencia histórica conocida).']]],
      ['ul', ['Las observaciones sirven para dejar anotado qué se hizo o a quién se le pidió la corrección.', 'Las marcas de una versión pasan solas a la siguiente del mismo mes. Las omitidas del mes anterior se traen con "Traer la revisión del cierre anterior".', 'El Excel trabajado del paso Exportar lleva todas las marcas y observaciones.']],
    ] },
    { clave: 'conciliacion', titulo: 'Qué significa cada resultado de la conciliación', icono: 'i-balanza', partes: [
      ['estados', [['chip ok', 'COINCIDE', 'SGA y ERP tienen el mismo saldo. Con el ERP de saldos abiertos, también cuando el comprobante no figura en ERP y su saldo en SGA es cero.'],
        ['chip error', 'DIFERENCIA', 'Los saldos no coinciden. Con el ERP de saldos abiertos, un comprobante de SGA con saldo que no figura en ERP se compara contra cero.'],
        ['chip warn', 'SOLO EN ERP', 'Figura con saldo en ERP pero no en SGA.'],
        ['chip', 'NO EVALUADO', 'Figura sólo en ERP, con saldo cero.'],
        ['chip warn', 'SIN COMPROBANTE EN SGA', 'Un movimiento de SGA sin número de comprobante: se revisa a mano.']]],
      ['p', 'Tipo PENDIENTE: un "movimiento pendiente de imputación" de SGA referido a una factura se muestra en su propia fila y no se suma al saldo del comprobante. Tipo RC-X, RC-R u OP-X: el recibo u orden de pago al que pertenece el subrecibo; el cruce se hace por subrecibo.'],
    ] },
    { clave: 'tramos', titulo: 'Archivos cortados en dos', icono: 'i-capas', partes: [
      ['p', 'Cuando un reporte tiene muchas filas, el sistema corta la descarga cerca de las 454.000 filas y entrega dos (o más) archivos que se complementan.'],
      ['ul', ['Agregá todos los archivos en la misma entrada: se leen en orden de nombre, como si fueran uno solo.', 'Si un archivo tiene justo alrededor de 450.000 filas, la herramienta te avisa que puede estar cortado.']],
    ] },
    { clave: 'datos', titulo: 'Dónde quedan los datos y cómo compartir', icono: 'i-carpeta', partes: [
      ['ul', ['Todo queda guardado en esta PC, en una carpeta propia de la herramienta (la ves en Configuración). No se sube a ningún lado.', 'Esa carpeta no se comparte ni se pone en OneDrive o SharePoint.', 'Para mandarle un cierre a otra persona usá "Exportar cierre": genera un archivo con los resultados trabajados. La otra persona lo abre con "Importar un cierre".', 'Tus Excel originales nunca se modifican.']],
    ] },
    { clave: 'faq', titulo: 'Preguntas frecuentes', icono: 'i-mensaje', partes: [
      ['qa', [['¿Tengo que renombrar los Excel?', 'No. Se reconocen por sus columnas.'],
        ['¿Puedo cerrar la pestaña mientras corre un reporte?', 'Sí. Sigue corriendo; al volver lo ves en el cierre o en el aviso de la barra de arriba.'],
        ['¿Qué pasa si corro un reporte de nuevo?', 'Se crea una versión nueva. Lo que revisaste en la anterior pasa solo a la nueva.'],
        ['¿La descarga de facturas es parte del cierre?', 'No. Es una herramienta aparte: la encontrás en la sección Facturas.'],
        ['¿Cómo cierro la herramienta?', 'Desde el menú de los tres puntos, "Cerrar la herramienta". Igual se apaga sola después de tres horas sin uso.']]],
    ] },
    { clave: 'problemas', titulo: 'Si algo sale mal', icono: 'i-alerta', partes: [
      ['qa', [['Un archivo dice "No reconocí qué reporte es"', 'Revisá que sea el Excel original descargado del sistema, sin modificar ni guardar con otro formato.'],
        ['"El archivo supera los … MB"', 'Subí el límite en Configuración (los históricos suelen pesar entre 50 y 100 MB).'],
        ['El reporte terminó con error', 'Leé el mensaje: casi siempre dice qué falta. Si no se entiende, abrí "Ver el detalle técnico" y mandá ese texto a quien te da soporte.'],
        ['Dice que se cerró la herramienta mientras corría', 'Volvé a correr el reporte: se crea una versión nueva con los mismos archivos.'],
        ['La página dice "Abrí la herramienta desde su acceso directo"', 'Cerrá la pestaña y abrila con el acceso directo "Reportes de cierre".']]],
    ] },
  ];

  function partesAyuda(partes) {
    const nodos = [];
    for (const [tipo, valor] of partes) {
      if (tipo === 'p') nodos.push(el('p', null, valor));
      else if (tipo === 'ul' || tipo === 'ol') nodos.push(el(tipo, null, valor.map(x => el('li', null, x))));
      else if (tipo === 'estados') nodos.push(el('div', { class: 'estado-ayuda' }, valor.flatMap(([clase, nombre, texto]) => [el('span', { class: clase }, nombre), el('span', null, texto)])));
      else if (tipo === 'qa') for (const [q, a] of valor) nodos.push(el('p', null, el('b', null, q), el('br'), a));
    }
    return nodos;
  }
  function acordeon(clave, titulo, cabeza, contenido, abierto) {
    return el('details', { class: 'acordeon', 'data-clave': clave, open: abierto },
      el('summary', null, cabeza, el('span', null, titulo), icono('i-abajo', 'flecha')),
      el('div', { class: 'contenido' }, contenido));
  }
  function abrirAyuda(clave = 'primeros') {
    const cajon = $('#cajon');
    limpiar(cajon);
    const cuerpo = el('div', { class: 'cajon-cuerpo' });
    const reportes = (estado.app ? estado.app.reportes : []);
    cuerpo.appendChild(el('p', { class: 'muted' }, 'Todo lo que necesitás para usar la herramienta. Tocá un tema para abrirlo.'));
    const general = AYUDA_GENERAL.slice(0, 2);
    for (const s of general) cuerpo.appendChild(acordeon(s.clave, s.titulo, el('span', { class: 'tile' }, icono(s.icono)), partesAyuda(s.partes), s.clave === clave));
    cuerpo.appendChild(el('h3', null, 'Los cinco pasos de cada reporte'));
    for (const [k, s] of Object.entries(AYUDA_PASOS)) cuerpo.appendChild(acordeon(k, s.titulo, el('span', { class: 'tile' }, icono(s.icono)), partesAyuda(s.partes), k === clave));
    cuerpo.appendChild(el('h3', null, 'Los reportes'));
    for (const r of reportes) {
      const contenido = [el('p', null, r.descripcion), r.ayuda ? el('p', null, r.ayuda) : null,
        el('p', null, el('b', null, 'Qué archivos pide')), el('ul', null, r.entradas.map(e => el('li', null, e.titulo + (e.ayuda ? ': ' + e.ayuda : '')))),
        el('p', null, el('b', null, 'Qué devuelve')), el('ul', null, [...new Set(r.salidas.map(s => s.titulo))].map(t => el('li', null, t))),
        r.ambito === 'herramienta' ? el('p', { class: 'muted' }, 'No es parte del cierre mensual: está en la sección Facturas.') : null];
      cuerpo.appendChild(acordeon('reporte-' + r.codigo, r.nombre, tileReporte(r), contenido, clave === 'reporte-' + r.codigo));
    }
    cuerpo.appendChild(el('h3', null, 'Más ayuda'));
    for (const s of AYUDA_GENERAL.slice(2)) cuerpo.appendChild(acordeon(s.clave, s.titulo, el('span', { class: 'tile' }, icono(s.icono)), partesAyuda(s.partes), s.clave === clave));
    cajon.append(el('div', { class: 'cajon-cabecera' }, icono('i-libro', 'g'), el('h2', null, 'Ayuda'),
      el('button', { type: 'button', class: 'barra-btn icono', 'aria-label': 'Cerrar la ayuda', onclick: cerrarAyuda }, icono('i-x'))), cuerpo);
    cajon.classList.add('abierto');
    cajon.setAttribute('aria-hidden', 'false');
    $('#velo-cajon').classList.add('visible');
    const objetivo = cuerpo.querySelector(`[data-clave="${clave}"]`);
    if (objetivo) { objetivo.classList.add('resaltado'); setTimeout(() => objetivo.scrollIntoView({ block: 'start', behavior: 'smooth' }), 120); }
  }
  function cerrarAyuda() {
    $('#cajon').classList.remove('abierto');
    $('#cajon').setAttribute('aria-hidden', 'true');
    $('#velo-cajon').classList.remove('visible');
  }
  $('#velo-cajon').addEventListener('click', cerrarAyuda);

  function acercaDe() {
    dialogo({ titulo: 'Reportes de cierre', texto: `Versión ${estado.app ? estado.app.version : ''}. Reúne los controles del cierre mensual: corre los mismos programas de siempre, guía cada reporte paso a paso y guarda la revisión y el historial en esta PC.`, boton: 'Cerrar', cancelar: null, tono: 'info' });
  }

  // ---------------------------------------------------------------- bienvenida
  function ilustracion(tipo) {
    const s = svg('svg', { viewBox: '0 0 160 124', class: 'ilustracion-guia', 'aria-hidden': 'true' });
    s.appendChild(svg('circle', { cx: '80', cy: '64', r: '58', class: 'ilu-fondo' }));
    if (tipo === 0) {
      s.append(svg('rect', { x: '44', y: '26', width: '72', height: '70', rx: '10', class: 'ilu-papel' }), svg('rect', { x: '44', y: '26', width: '72', height: '20', rx: '10', class: 'ilu-naranja' }),
        svg('rect', { x: '44', y: '38', width: '72', height: '8', class: 'ilu-naranja' }), svg('rect', { x: '58', y: '18', width: '6', height: '16', rx: '3', class: 'ilu-acento' }), svg('rect', { x: '96', y: '18', width: '6', height: '16', rx: '3', class: 'ilu-acento' }),
        svg('circle', { cx: '80', cy: '71', r: '16', class: 'ilu-ok' }), svg('path', { d: 'M72 71l6 6 11-12', class: 'ilu-tilde' }));
    } else if (tipo === 1) {
      const pos = [[34, 30], [86, 30], [34, 70], [86, 70]];
      pos.forEach(([x, y], i) => s.append(svg('rect', { x: String(x), y: String(y), width: '42', height: '30', rx: '8', class: 'ilu-papel' }), svg('rect', { x: String(x + 8), y: String(y + 8), width: '14', height: '14', rx: '4', class: i % 2 ? 'ilu-naranja' : 'ilu-acento' }), svg('rect', { x: String(x + 25), y: String(y + 11), width: '10', height: '3', rx: '1.5', class: 'ilu-gris' }), svg('rect', { x: String(x + 25), y: String(y + 17), width: '7', height: '3', rx: '1.5', class: 'ilu-gris' })));
    } else if (tipo === 2) {
      s.appendChild(svg('path', { d: 'M30 64h100', class: 'ilu-trazo' }));
      [30, 55, 80, 105, 130].forEach((x, i) => s.appendChild(svg('circle', { cx: String(x), cy: '64', r: i === 2 ? '15' : '10', class: i < 2 ? 'ilu-ok' : i === 2 ? 'ilu-acento' : 'ilu-papel' })));
      s.append(svg('path', { d: 'M26 64l3 3 5-6', class: 'ilu-tilde' }), svg('path', { d: 'M51 64l3 3 5-6', class: 'ilu-tilde' }), svg('path', { d: 'M73 64l5 5 9-10', class: 'ilu-tilde' }));
    } else {
      s.append(svg('rect', { x: '30', y: '28', width: '100', height: '70', rx: '10', class: 'ilu-papel' }));
      [40, 58, 76].forEach((y, i) => s.append(svg('rect', { x: '40', y: String(y), width: '14', height: '12', rx: '3', class: i < 2 ? 'ilu-ok' : 'ilu-gris' }), svg('rect', { x: '60', y: String(y + 3), width: '58', height: '6', rx: '3', class: 'ilu-gris' })));
      s.append(svg('path', { d: 'M43 46l3 3 5-6', class: 'ilu-tilde' }), svg('path', { d: 'M43 64l3 3 5-6', class: 'ilu-tilde' }));
    }
    return s;
  }
  function bienvenida(alTerminar) {
    if (estado.bienvenidaAbierta) return;
    estado.bienvenidaAbierta = true;
    const diapos = [
      { titulo: 'Te damos la bienvenida', texto: 'Esta herramienta reúne los controles del cierre mensual en un solo lugar. Te guía paso a paso y guarda todo lo que hacés, mes a mes.' },
      { titulo: 'Un cierre por mes', texto: 'Creás el cierre del mes con su fecha de corte. Adentro están los cuatro reportes: Conciliación general, Controles SGA, Control de Mora y Control de cheques.' },
      { titulo: 'Cada reporte, en cinco pasos', texto: 'Elegís los Excel descargados, revisás las opciones, lo corrés, revisás los resultados y descargás el Excel trabajado.' },
      { titulo: 'La revisión queda guardada', texto: 'Marcá cada fila como revisada u omitida y anotá observaciones. Lo que marques pasa solo a la próxima versión del mes. La ayuda está siempre arriba a la derecha.' },
    ];
    let i = 0;
    const contenedor = el('div', { class: 'bienvenida' });
    const puntos = el('div', { class: 'puntos-guia' }, diapos.map(() => el('span')));
    const atras = btn('Atrás', () => { if (i > 0) { i--; pintar(); } }, 'fantasma');
    const siguiente = btn('Siguiente', () => { if (i < diapos.length - 1) { i++; pintar(); } else { terminar(true); } }, 'primario');
    const pintar = () => {
      limpiar(contenedor).appendChild(el('div', { class: 'diapo' }, ilustracion(i), el('h2', null, diapos[i].titulo), el('p', null, diapos[i].texto)));
      contenedor.appendChild(puntos);
      [...puntos.children].forEach((p, k) => p.classList.toggle('activo', k === i));
      atras.disabled = i === 0;
      limpiar(siguiente).appendChild(el('span', null, i === diapos.length - 1 ? 'Empezar' : 'Siguiente'));
      siguiente.appendChild(icono(i === diapos.length - 1 ? 'i-check' : 'i-der'));
    };
    let terminado = false;
    const terminar = empezar => {
      if (terminado) return;
      terminado = true;
      estado.bienvenidaAbierta = false;
      modal.cerrar();
      api('PATCH', '/api/configuracion', { bienvenida: true }).catch(() => {});
      if (estado.conf) estado.conf.bienvenida = true;
      if (alTerminar) alTerminar(empezar);
    };
    const modal = abrirModal({ titulo: 'Guía de inicio', iconoNombre: 'i-chispa', cuerpo: contenedor,
      pie: [el('div', { class: 'izq' }, btn('Saltar la guía', () => terminar(false), 'enlace')), atras, siguiente],
      alCerrar: () => { estado.bienvenidaAbierta = false; if (!terminado) { terminado = true; api('PATCH', '/api/configuracion', { bienvenida: true }).catch(() => {}); if (estado.conf) estado.conf.bienvenida = true; } } });
    pintar();
  }

  // ---------------------------------------------------------------- nuevo cierre
  async function nuevoCierre(periodoInicial) {
    const cierres = await api('GET', '/api/cierres');
    const existentes = new Set(cierres.map(c => c.periodo));
    const actual = periodoDe(hoy());
    let elegido = periodoInicial || (existentes.has(actual) ? null : actual);
    let anio = parseInt((elegido || actual).slice(0, 4), 10);
    let corteEditado = false;
    const corte = el('input', { type: 'date', id: 'nuevo-corte', value: elegido ? finDeMes(elegido) : '', oninput: () => { corteEditado = true; previa(); } });
    const titulo = el('b');
    const meses = el('div', { class: 'meses', role: 'group', 'aria-label': 'Mes del cierre' });
    const vista = el('div', { class: 'vista-previa' });
    const crear = btn('Crear el cierre', null, 'primario', { icono: 'i-mas' });
    const pintarMeses = () => {
      titulo.textContent = String(anio);
      limpiar(meses);
      MESES.forEach((m, k) => {
        const p = `${anio}-${String(k + 1).padStart(2, '0')}`;
        const ya = existentes.has(p);
        meses.appendChild(el('button', { type: 'button', class: (p === elegido ? 'elegido ' : '') + (p === actual ? 'actual' : ''), disabled: ya, title: ya ? 'Ese cierre ya existe' : null,
          onclick: () => { elegido = p; if (!corteEditado) corte.value = finDeMes(p); pintarMeses(); previa(); } }, m.slice(0, 3).replace(/^./, c => c.toUpperCase())));
      });
    };
    const previa = () => {
      limpiar(vista);
      if (!elegido) { vista.append(icono('i-info'), el('span', null, 'Elegí el mes del cierre.')); crear.disabled = true; return; }
      vista.append(icono('i-cierre', 'g'), el('span', null, 'Se va a crear el cierre de ', el('b', null, periodoLargo(elegido)), corte.value ? [' con fecha de corte ', el('b', null, fechaLarga(corte.value)), '.'] : '. Falta la fecha de corte.'));
      crear.disabled = !corte.value;
    };
    const cuerpo = el('div', null,
      el('p', { class: 'muted' }, 'Elegí el mes. La fecha de corte se propone como el último día del mes; se usa en cada reporte y se puede cambiar.'),
      el('div', { class: 'selector-anio' }, btn('', () => { anio--; pintarMeses(); }, 'fantasma icono', { icono: 'i-izq', aria: 'Año anterior' }), titulo, btn('', () => { anio++; pintarMeses(); }, 'fantasma icono', { icono: 'i-der', aria: 'Año siguiente' })),
      meses,
      el('div', { class: 'campo', style: 'margin-top:16px;max-width:260px' }, el('label', { for: 'nuevo-corte' }, 'Fecha de corte'), corte),
      vista);
    const m = abrirModal({ titulo: 'Nuevo cierre', iconoNombre: 'i-calendario', cuerpo, pie: [btn('Cancelar', () => m.cerrar(), 'fantasma'), crear] });
    crear.addEventListener('click', async () => {
      crear.disabled = true;
      try {
        const c = await api('POST', '/api/cierres', { periodo: elegido, corte: corte.value });
        m.cerrar();
        aviso(`Listo: se creó el cierre de ${periodoLargo(c.periodo)}.`, 'ok');
        location.hash = '#/cierre/' + encodeURIComponent(c.id);
      } catch (e) { avisarError(e); crear.disabled = false; }
    });
    pintarMeses();
    previa();
  }

  // ---------------------------------------------------------------- enrutador y eventos
  function enrutar() {
    const partes = location.hash.replace(/^#\/?/, '').split('/').map(decodeURIComponent);
    const vista = partes[0] || 'inicio';
    const nav = { inicio: 'inicio', cierre: 'inicio', ejecucion: 'inicio', facturas: 'facturas', historial: 'historial', configuracion: 'configuracion' }[vista];
    for (const a of document.querySelectorAll('[data-nav]')) a.classList.toggle('activa', a.dataset.nav === nav);
    $('#vista').classList.toggle('ancha', vista === 'ejecucion');
    estado.vista = { nombre: vista, partes };
    detenerSondeo();
    cerrarMenu();
    const r = { inicio: vistaInicio, cierre: () => vistaCierre(partes[1]), ejecucion: () => vistaEjecucion(partes[1], partes[2]), facturas: vistaFacturas, historial: vistaHistorial, configuracion: vistaConfiguracion }[vista];
    (r || vistaInicio)().catch(avisarError);
  }
  function detenerSondeo() { if (estado.sondeo) { clearInterval(estado.sondeo); estado.sondeo = null; } }
  function conectarEventos() {
    if (estado.fuente) estado.fuente.close();
    const f = new EventSource('/api/eventos');
    estado.fuente = f;
    f.addEventListener('trabajo', ev => { const t = JSON.parse(ev.data); actualizarIndicador(); if (estado.w && estado.w.e && estado.w.e.trabajoId === t.id) pintarTrabajo(t); });
    f.addEventListener('ejecucion', ev => {
      const e = JSON.parse(ev.data);
      actualizarIndicador();
      if (estado.w && estado.w.e && estado.w.e.id === e.id && !e.borrado) {
        const antes = estado.w.e.estado;
        if (antes !== e.estado) {
          if (e.estado === 'ok' && (antes === 'corriendo' || antes === 'esperando')) { fiesta(); aviso(`${estado.w.reporte.nombre}: terminó bien. Ya podés revisar los resultados.`, 'ok'); }
          vistaEjecucion(e.id, e.estado === 'ok' ? '4' : undefined, true).catch(avisarError);
        }
      } else if (estado.vista && ['inicio', 'cierre', 'historial', 'facturas'].includes(estado.vista.nombre)) enrutar();
    });
    f.addEventListener('cierre', () => { if (estado.vista && estado.vista.nombre === 'inicio') enrutar(); });
    f.onerror = () => { setTimeout(() => { if (estado.fuente === f) conectarEventos(); }, 5000); };
  }
  async function actualizarIndicador() {
    try {
      const activos = (await api('GET', '/api/trabajos')).filter(t => t.estado === 'corriendo' || t.estado === 'esperando');
      const ind = $('#indicador');
      ind.classList.toggle('oculto', activos.length === 0);
      if (activos.length) {
        const espera = activos.some(t => t.estado === 'esperando');
        ind.classList.toggle('espera', espera);
        $('#indicador-texto').textContent = espera ? 'Un reporte espera tu acción' : activos.length === 1 ? 'Un reporte corriendo' : `${activos.length} reportes corriendo`;
        ind.href = `#/ejecucion/${encodeURIComponent((activos.find(t => t.estado === 'esperando') || activos[0]).ejecucionId)}/3`;
      }
    } catch (e) { /* informativo */ }
  }

  // ---------------------------------------------------------------- piezas comunes
  function claseEstado(info) {
    if (!info || !info.ultima) return '';
    if (info.final) return 'final';
    const e = info.ultima.estado;
    return e === 'ok' ? 'hecho' : (e === 'corriendo' || e === 'esperando') ? 'curso' : e === 'error' ? 'error' : '';
  }
  function chipEstado(e) {
    const mapa = { ok: ['ok', 'i-check-circulo'], error: ['error', 'i-x-circulo'], corriendo: ['warn', 'i-reloj'], esperando: ['warn', 'i-mano'], cancelado: ['', 'i-detener'], borrador: ['borde', 'i-lapiz'], listo: ['borde', 'i-lapiz'] };
    const [clase, ic] = mapa[e.estado] || ['', 'i-info'];
    return el('span', { class: 'chip ' + clase }, icono(ic), ESTADO_TEXTO[e.estado] || e.estado);
  }
  function barraRevision(rev) {
    const total = rev.pendientes + rev.revisadas + rev.omitidas;
    const pct = v => total ? (v / total * 100).toFixed(2) + '%' : '0';
    return el('div', { class: 'barra-revision', title: `${n(rev.revisadas)} revisadas, ${n(rev.omitidas)} omitidas, ${n(rev.pendientes)} pendientes` },
      el('span', { class: 'rev', style: `width:${pct(rev.revisadas)}` }), el('span', { class: 'omi', style: `width:${pct(rev.omitidas)}` }));
  }
  function anillo(valor, total, etiqueta) {
    const r = 48, c = 2 * Math.PI * r;
    const pct = total ? valor / total : 0;
    const arco = svg('circle', { cx: '59', cy: '59', r: String(r), class: 'valor', 'stroke-dasharray': String(c), 'stroke-dashoffset': String(c) });
    const nodo = el('div', { class: 'anillo' + (total && valor === total ? ' completo' : ''), role: 'img', 'aria-label': `${valor} de ${total} ${etiqueta}` },
      svg('svg', { viewBox: '0 0 118 118' }, svg('circle', { cx: '59', cy: '59', r: String(r), class: 'pista' }), arco),
      el('div', { class: 'centro' }, el('b', null, `${valor}/${total}`), el('span', null, etiqueta)));
    requestAnimationFrame(() => requestAnimationFrame(() => arco.setAttribute('stroke-dashoffset', String(c * (1 - pct)))));
    return nodo;
  }
  const reportesCierre = () => estado.app.reportes.filter(r => r.ambito !== 'herramienta');
  function resumenCierre(c) {
    const lista = reportesCierre();
    let finales = 0, terminados = 0, curso = 0, pendientesRev = 0;
    for (const r of lista) {
      const info = c.reportes[r.codigo];
      if (!info || !info.ultima) continue;
      const u = info.final || info.ultima;
      if (info.final) finales++;
      else if (u.estado === 'ok') terminados++;
      else if (u.estado === 'corriendo' || u.estado === 'esperando') curso++;
      if (u.estado === 'ok') pendientesRev += u.revision.pendientes;
    }
    return { total: lista.length, finales, terminados, curso, sinCorrer: lista.length - finales - terminados - curso, pendientesRev };
  }

  // ---------------------------------------------------------------- vista: inicio (cierres)
  async function vistaInicio() {
    const sello = nuevoSello();
    estado.w = null;
    const [cierres, app] = await Promise.all([api('GET', '/api/cierres'), api('GET', '/api/estado')]);
    if (!vigente(sello)) return;
    estado.app = app;
    const main = limpiar($('#vista'));
    const actual = periodoDe(hoy());
    const enCurso = cierres.find(c => !c.cerrado && !c.importado) || null;
    const contenedor = el('div', { class: 'escalonado' });
    main.appendChild(contenedor);
    const importar = el('input', { type: 'file', accept: '.zip', class: 'visual-oculto', 'aria-label': 'Importar un cierre exportado' });
    importar.addEventListener('change', async () => {
      const f = importar.files[0];
      if (!f) return;
      try { const c = await api('POST', '/api/cierres/importar', f, { crudo: true, cabeceras: { 'Content-Type': 'application/zip' } }); aviso(`Se importó el cierre de ${periodoLargo(c.periodo)} (sólo para ver).`, 'ok'); enrutar(); } catch (e) { avisarError(e); }
      importar.value = '';
    });
    if (!enCurso) {
      contenedor.appendChild(el('section', { class: 'hero' }, el('div', { class: 'hero-cuadricula' }), el('div', { class: 'hero-brillo' }),
        el('div', { class: 'hero-texto' },
          el('span', { class: 'hero-etiqueta' }, icono('i-chispa'), cierres.length ? 'Todo al día' : 'Para empezar'),
          el('h1', null, cierres.length ? `Empezá el cierre de ${periodoLargo(actual).toLowerCase()}` : 'Empezá tu primer cierre'),
          el('p', { class: 'bajada' }, 'Un cierre agrupa los cuatro reportes del mes. Lo creás con su fecha de corte y después corrés cada reporte paso a paso.'),
          el('div', { class: 'acciones-fila' },
            btn(`Crear el cierre de ${periodoLargo(actual).toLowerCase()}`, () => nuevoCierre(cierres.some(c => c.periodo === actual) ? null : actual).catch(avisarError), 'primario grande llama', { icono: 'i-mas' }),
            btn('Ver cómo funciona', () => bienvenida(), 'fantasma', { icono: 'i-libro' }))),
        el('div', { class: 'hero-anillo' }, el('div', { class: 'tile grande', style: 'width:96px;height:96px;border-radius:26px;background:var(--panel);color:var(--accent);box-shadow:var(--sombra-media)' }, icono('i-cierre', 'xg')))));
    } else {
      const res = resumenCierre(enCurso);
      const listos = res.finales + res.terminados;
      const bajada = res.sinCorrer === res.total ? 'Todavía no corriste ningún reporte de este cierre. Empezá por el que tengas los archivos listos.'
        : res.finales === res.total ? 'Los cuatro reportes tienen su resultado final. El cierre está completo.'
        : `Faltan ${res.total - listos === 1 ? 'un reporte' : (res.total - listos) + ' reportes'} por correr` + (res.pendientesRev ? (res.pendientesRev === 1 ? ' y hay una fila pendiente de revisar.' : ` y hay ${n(res.pendientesRev)} filas pendientes de revisar.`) : '.');
      contenedor.appendChild(el('section', { class: 'hero' }, el('div', { class: 'hero-cuadricula' }), el('div', { class: 'hero-brillo' }),
        el('div', { class: 'hero-texto' },
          el('span', { class: 'hero-etiqueta' }, icono('i-calendario'), 'Cierre en curso'),
          el('h1', null, periodoLargo(enCurso.periodo)),
          el('p', { class: 'bajada' }, `Fecha de corte: ${fechaLarga(enCurso.corte)}. ${bajada}`),
          el('div', { class: 'acciones-fila' }, enlace('Continuar el cierre', '#/cierre/' + encodeURIComponent(enCurso.id), 'btn primario grande', 'i-der'),
            enCurso.periodo < actual && !cierres.some(c => c.periodo === actual) ? btn(`Crear el de ${periodoLargo(actual).toLowerCase()}`, () => nuevoCierre(actual).catch(avisarError), 'fantasma', { icono: 'i-mas' }) : null)),
        el('div', { class: 'hero-anillo' }, anillo(listos, res.total, 'reportes listos'),
          el('div', { class: 'anillo-leyenda' },
            el('div', null, el('span', { class: 'cuadro', style: 'background:var(--accent)' }), `${res.finales} con resultado final`),
            el('div', null, el('span', { class: 'cuadro', style: 'background:var(--ok)' }), `${res.terminados} ${res.terminados === 1 ? 'terminado' : 'terminados'}`),
            el('div', null, el('span', { class: 'cuadro', style: 'background:var(--warn)' }), `${res.curso} en curso`),
            el('div', null, el('span', { class: 'cuadro', style: 'background:var(--line2)' }), `${res.sinCorrer} sin correr`)))));
    }
    contenedor.appendChild(el('div', { class: 'titulo-seccion' }, el('h2', null, 'Todos los cierres'), el('span', { class: 'cuenta' }, String(cierres.length)),
      el('div', { class: 'acciones-fila', style: 'margin-left:auto' }, btn('Importar un cierre', () => importar.click(), 'fantasma chico', { icono: 'i-bajar' }), importar,
        btn('Nuevo cierre', () => nuevoCierre().catch(avisarError), 'chico', { icono: 'i-mas' }))));
    if (!cierres.length) {
      contenedor.appendChild(el('div', { class: 'vacio' }, el('div', { class: 'ilustracion' }, icono('i-calendario')), el('h2', null, 'Todavía no hay cierres'), el('p', null, 'Cuando crees el primero, va a aparecer acá junto con el estado de sus reportes.')));
    }
    const lista = el('div', { class: 'escalonado' });
    for (const c of cierres) {
      const m = /^(\d{4})-(\d{2})$/.exec(c.periodo) || [];
      const res = resumenCierre(c);
      lista.appendChild(el('a', { class: 'tarjeta fila-cierre', href: '#/cierre/' + encodeURIComponent(c.id) },
        el('div', { class: 'hoja-mes', 'aria-hidden': 'true' }, el('span', { class: 'mes' }, (MESES[parseInt(m[2], 10) - 1] || '').slice(0, 3).toUpperCase()), el('span', { class: 'anio' }, m[1] || '')),
        el('div', null, el('div', { class: 'nombre' }, periodoLargo(c.periodo)), el('div', { class: 'detalle' }, `Corte ${fechaCorta(c.corte)}` + (c.importado ? ' · importado' : '') + (c.cerrado ? ' · completo' : ''))),
        el('div', { class: 'mini-reportes' }, reportesCierre().map(r => {
          const info = c.reportes[r.codigo];
          return el('span', { class: 'mini-reporte ' + claseEstado(info), title: textoEstadoReporte(info, r) }, tileReporte(r), info && info.final ? 'Final' : info && info.ultima ? (ESTADO_TEXTO[info.ultima.estado] || '') : 'Sin correr');
        })),
        el('span', { class: 'chip ' + (res.finales === res.total ? 'ok' : 'borde') }, `${res.finales + res.terminados}/${res.total}`)));
    }
    contenedor.appendChild(lista);
    if (estado.conf && !estado.conf.bienvenida) bienvenida(empezar => { if (empezar && !cierres.length) nuevoCierre(actual).catch(avisarError); });
  }
  function textoEstadoReporte(info, r) {
    if (!info || !info.ultima) return `${r.nombre}: sin correr`;
    const u = info.final || info.ultima;
    return `${r.nombre}: ${ESTADO_TEXTO[u.estado] || u.estado}, versión ${u.version}` + (u.estado === 'ok' ? (u.revision.pendientes === 1 ? ', una fila pendiente' : `, ${n(u.revision.pendientes)} filas pendientes`) : '') + (info.final ? ', resultado final' : '');
  }

  // ---------------------------------------------------------------- vista: cierre
  async function vistaCierre(id) {
    const sello = nuevoSello();
    estado.w = null;
    const [c, app] = await Promise.all([api('GET', '/api/cierres/' + encodeURIComponent(id)), api('GET', '/api/estado')]);
    if (!vigente(sello)) return;
    estado.app = app;
    if (c.herramienta) { location.hash = '#/facturas'; return; }
    const main = limpiar($('#vista'));
    const res = resumenCierre(c);
    const editar = async () => {
      const corte = el('input', { type: 'date', id: 'editar-corte', value: c.corte });
      const notas = el('textarea', { id: 'editar-notas', rows: '4' });
      notas.value = c.notas || '';
      const m = abrirModal({ titulo: `Cierre de ${periodoLargo(c.periodo)}`, iconoNombre: 'i-lapiz', cuerpo: el('div', null,
        el('div', { class: 'campo', style: 'max-width:260px' }, el('label', { for: 'editar-corte' }, 'Fecha de corte'), corte, el('span', { class: 'ayuda' }, 'Se propone en cada reporte nuevo de este cierre.')),
        el('div', { class: 'campo' }, el('label', { for: 'editar-notas' }, 'Notas del cierre'), notas, el('span', { class: 'ayuda' }, 'Lo que quieras recordar de este mes.'))),
        pie: [btn('Cancelar', () => m.cerrar(), 'fantasma'), btn('Guardar', async () => { try { await api('PATCH', '/api/cierres/' + encodeURIComponent(c.id), { corte: corte.value, notas: notas.value }); m.cerrar(); aviso('Cambios guardados.', 'ok'); enrutar(); } catch (e) { avisarError(e); } }, 'primario', { icono: 'i-check' })] });
    };
    const acciones = [
      { icono: 'i-lapiz', texto: 'Editar fecha de corte y notas', onclick: editar },
      { icono: 'i-caja', texto: 'Exportar el cierre', detalle: 'Un archivo para compartirlo con otra persona', onclick: () => { location.href = `/api/cierres/${encodeURIComponent(c.id)}/exportar`; } },
      { icono: c.cerrado ? 'i-deshacer' : 'i-bandera', texto: c.cerrado ? 'Reabrir el cierre' : 'Marcar el cierre como completo', onclick: async () => { try { await api('PATCH', '/api/cierres/' + encodeURIComponent(c.id), { cerrado: !c.cerrado }); if (!c.cerrado) { fiesta(); aviso(`Cierre de ${periodoLargo(c.periodo)} completo.`, 'ok'); } enrutar(); } catch (e) { avisarError(e); } } },
      'sep',
      { icono: 'i-basura', texto: 'Borrar el cierre', peligro: true, onclick: async () => {
        const tieneFinal = Object.values(c.reportes).some(r => r.final);
        if (!await confirmar('¿Borrar este cierre?', (tieneFinal ? 'Tiene resultados finales. ' : '') + 'Se pierden todas sus corridas, archivos y revisiones. No se puede deshacer.', 'Borrar el cierre', 'peligro')) return;
        try { await api('DELETE', `/api/cierres/${encodeURIComponent(c.id)}?forzar=1`); aviso('Cierre borrado.', 'ok'); location.hash = '#/inicio'; } catch (e) { avisarError(e); }
      } },
    ];
    const listos = res.finales + res.terminados;
    main.appendChild(el('div', { class: 'migas' }, el('a', { href: '#/inicio' }, 'Cierres'), icono('i-der'), el('span', null, periodoLargo(c.periodo))));
    main.appendChild(el('section', { class: 'hero entrar' }, el('div', { class: 'hero-cuadricula' }), el('div', { class: 'hero-brillo' }),
      el('div', { class: 'hero-texto' },
        el('span', { class: 'hero-etiqueta' }, icono(c.cerrado ? 'i-check-circulo' : 'i-calendario'), c.importado ? 'Cierre importado (sólo para ver)' : c.cerrado ? 'Cierre completo' : 'Cierre en curso'),
        el('h1', null, periodoLargo(c.periodo)),
        el('p', { class: 'bajada' }, `Fecha de corte: ${fechaLarga(c.corte)}.` + (c.notas ? ` ${c.notas}` : '')),
        el('div', { class: 'acciones-fila' }, c.importado ? null : btn('Editar', editar, 'fantasma chico', { icono: 'i-lapiz' }), btn('Ayuda: cómo es un cierre', () => abrirAyuda('primeros'), 'fantasma chico', { icono: 'i-ayuda' }), botonMenu(acciones, 'Acciones del cierre'))),
      el('div', { class: 'hero-anillo' }, anillo(listos, res.total, 'reportes listos'),
        el('div', { class: 'anillo-leyenda' },
          el('div', null, el('span', { class: 'cuadro', style: 'background:var(--accent)' }), `${res.finales} con resultado final`),
          el('div', null, el('span', { class: 'cuadro', style: 'background:var(--ok)' }), `${res.terminados} ${res.terminados === 1 ? 'terminado' : 'terminados'}`),
          el('div', null, el('span', { class: 'cuadro', style: 'background:var(--line2)' }), `${res.sinCorrer + res.curso} por hacer`)))));
    main.appendChild(el('div', { class: 'titulo-seccion' }, el('h2', null, 'Reportes del cierre')));
    const grilla = el('div', { class: 'grilla-2 escalonado' });
    for (const r of reportesCierre()) grilla.appendChild(tarjetaReporte(c, r));
    main.appendChild(grilla);
  }
  function tarjetaReporte(c, r) {
    const info = c.reportes[r.codigo] || { versiones: 0, ultima: null, final: null };
    const u = info.ultima;
    const clase = claseEstado(info);
    const tarjeta = el('article', { class: 'tarjeta tarjeta-reporte ' + clase });
    const estadoFila = el('div', { class: 'estado' });
    if (!u) estadoFila.appendChild(el('span', { class: 'chip borde' }, icono('i-reloj'), 'Sin correr este mes'));
    else {
      estadoFila.appendChild(chipEstado(u));
      estadoFila.appendChild(el('span', { class: 'chip borde' }, `Versión ${u.version}`));
      if (info.final) estadoFila.appendChild(el('span', { class: 'chip acento' }, icono('i-bandera'), info.final.version === u.version ? 'Resultado final' : `Final: versión ${info.final.version}`));
    }
    const abrir = (e, paso) => { location.hash = '#/ejecucion/' + encodeURIComponent(e.id) + (paso ? '/' + paso : ''); };
    const nueva = async base => {
      try {
        const e = await api('POST', '/api/ejecuciones', { cierre: c.id, reporte: r.codigo });
        if (base) await api('PATCH', '/api/ejecuciones/' + encodeURIComponent(e.id), { entradas: base.entradas || {}, parametros: base.parametros || {} });
        abrir(e, base ? '2' : '1');
      } catch (err) { avisarError(err); }
    };
    let principal = null;
    const secundarios = [];
    if (c.importado) { if (u && u.estado === 'ok') principal = btn('Ver resultados', () => abrir(u, '4'), 'primario', { icono: 'i-tabla' }); }
    else if (!u) principal = btn('Empezar', () => nueva(null), 'primario', { icono: 'i-play' });
    else if (u.estado === 'borrador' || u.estado === 'listo') principal = btn('Continuar', () => abrir(u), 'primario', { icono: 'i-der' });
    else if (u.estado === 'corriendo' || u.estado === 'esperando') principal = btn(u.estado === 'esperando' ? 'Ver qué necesita' : 'Ver el avance', () => abrir(u, '3'), 'primario', { icono: u.estado === 'esperando' ? 'i-mano' : 'i-reloj' });
    else if (u.estado === 'ok') { principal = btn('Revisar resultados', () => abrir(u, '4'), 'primario', { icono: 'i-tabla' }); secundarios.push(btn('Correr de nuevo', () => nueva(u), 'fantasma chico', { icono: 'i-refrescar' })); }
    else { principal = btn('Volver a correr', () => nueva(u), 'primario', { icono: 'i-refrescar' }); secundarios.push(btn('Ver qué pasó', () => abrir(u, '3'), 'fantasma chico', { icono: 'i-info' })); }
    tarjeta.append(el('div', { class: 'cabeza' }, tileReporte(r), el('div', null, el('h3', null, r.nombre), el('div', { class: 'desc' }, r.descripcion))), estadoFila);
    if (u && u.estado === 'ok') {
      const rev = u.revision;
      tarjeta.append(barraRevision(rev), el('div', { class: 'leyenda-revision' }, el('span', null, el('b', null, n(rev.pendientes)), ' pendientes'), el('span', null, el('b', null, n(rev.revisadas)), ' revisadas'), el('span', null, el('b', null, n(rev.omitidas)), ' omitidas')));
    }
    tarjeta.appendChild(el('div', { class: 'pie' }, el('div', { class: 'acciones-fila' }, principal, secundarios),
      el('div', { class: 'acciones-fila' }, info.versiones > 1 ? enlace(`${info.versiones} versiones`, '#/historial/' + encodeURIComponent(c.id) + '/' + r.codigo, 'btn enlace chico', 'i-historial') : null,
        el('button', { type: 'button', class: 'btn fantasma icono', title: 'Ayuda de este reporte', 'aria-label': 'Ayuda de ' + r.nombre, onclick: () => abrirAyuda('reporte-' + r.codigo) }, icono('i-ayuda')))));
    return tarjeta;
  }

  // ---------------------------------------------------------------- vista: facturas
  async function vistaFacturas() {
    const sello = nuevoSello();
    estado.w = null;
    const [esp, app] = await Promise.all([api('GET', '/api/herramientas/descarga_facturas'), api('GET', '/api/estado')]);
    if (!vigente(sello)) return;
    estado.app = app;
    const r = app.reportes.find(x => x.codigo === 'descarga_facturas');
    const main = limpiar($('#vista'));
    const nueva = async () => {
      try { const e = await api('POST', '/api/ejecuciones', { cierre: esp.id, reporte: r.codigo }); location.hash = '#/ejecucion/' + encodeURIComponent(e.id) + '/1'; } catch (err) { avisarError(err); }
    };
    main.appendChild(el('section', { class: 'hero entrar' }, el('div', { class: 'hero-brillo' }),
      el('div', { class: 'hero-texto' }, el('span', { class: 'hero-etiqueta' }, icono('i-factura'), 'Herramienta aparte del cierre'),
        el('h1', null, r.nombre), el('p', { class: 'bajada' }, r.descripcion),
        el('div', { class: 'acciones-fila' }, r.disponible ? btn('Nueva descarga', nueva, 'primario grande', { icono: 'i-mas' }) : btn('Cómo instalarla', () => instalarFacturas(), 'primario grande', { icono: 'i-info' }),
          btn('Ayuda', () => abrirAyuda('reporte-' + r.codigo), 'fantasma', { icono: 'i-ayuda' }))),
      el('div', { class: 'hero-anillo' }, tileReporte(r, 'grande'))));
    if (!r.disponible) main.appendChild(el('div', { class: 'caja-info entrar' }, icono('i-info', 'g'), el('div', null, el('p', null, el('b', null, 'Todavía no está instalada. '), r.motivo), el('p', { class: 'muted' }, 'La descarga usa el Chrome de la PC y lee los PDF de las facturas; por eso se instala por separado, una sola vez.'))));
    const lista = esp.ejecuciones || [];
    main.appendChild(el('div', { class: 'titulo-seccion' }, el('h2', null, 'Descargas anteriores'), el('span', { class: 'cuenta' }, String(lista.length))));
    if (!lista.length) {
      main.appendChild(el('div', { class: 'vacio' }, el('div', { class: 'ilustracion' }, icono('i-factura')), el('h2', null, 'Todavía no hiciste ninguna descarga'), el('p', null, 'Cada descarga queda registrada acá, con su resultado.')));
      return;
    }
    main.appendChild(tablaEjecuciones(lista, { mostrarCierre: false }));
  }
  function instalarFacturas() {
    dialogo({ titulo: 'Instalar la descarga de facturas', texto: 'Cerrá la herramienta, abrí la carpeta del programa y hacé doble clic en "Instalar descarga de facturas.bat". Tarda unos minutos y se hace una sola vez. Después volvé a abrir la herramienta.', boton: 'Entendido', cancelar: null, tono: 'info' });
  }

  // ---------------------------------------------------------------- vista: ejecución (asistente)
  async function vistaEjecucion(id, pasoPedido, refresco = false) {
    const sello = nuevoSello();
    detenerSondeo();
    const e = await api('GET', '/api/ejecuciones/' + encodeURIComponent(id));
    if (!estado.app) estado.app = await api('GET', '/api/estado');
    const cierre = await api('GET', '/api/cierres/' + encodeURIComponent(e.cierreId));
    if (!vigente(sello)) return;
    const reporte = estado.app.reportes.find(r => r.codigo === e.reporte);
    const previo = estado.w && estado.w.e && estado.w.e.id === e.id ? estado.w : null;
    const w = { e, reporte, cierre, paso: 1, tablas: null, tabla: previo ? previo.tabla : null,
      grilla: previo ? previo.grilla : { desde: 0, cantidad: 100, orden: null, desc: false, filtro: '', estado: '', columna: '', seleccion: new Set() },
      valores: previo ? previo.valores : null, trabajo: null };
    estado.w = w;
    const terminal = ['ok', 'error', 'cancelado'].includes(e.estado);
    const enCurso = e.estado === 'corriendo' || e.estado === 'esperando';
    const pasoDefault = e.estado === 'ok' ? 4 : (enCurso || terminal) ? 3 : (Object.keys(e.entradas || {}).length ? 2 : 1);
    let paso = parseInt(pasoPedido || '', 10) || (previo && !refresco ? previo.paso : pasoDefault);
    if (!terminal && !enCurso && paso > 2) paso = pasoDefault;
    if ((paso === 4 || paso === 5) && e.estado !== 'ok') paso = 3;
    w.paso = paso;
    const main = limpiar($('#vista'));
    const esHerramienta = !!cierre.herramienta;
    const volver = esHerramienta ? '#/facturas' : '#/cierre/' + encodeURIComponent(cierre.id);
    main.appendChild(el('div', { class: 'migas' }, esHerramienta ? el('a', { href: '#/facturas' }, 'Facturas') : [el('a', { href: '#/inicio' }, 'Cierres'), icono('i-der'), el('a', { href: volver }, periodoLargo(cierre.periodo))],
      icono('i-der'), el('span', null, `${reporte.nombre}, versión ${e.version}`)));
    main.appendChild(el('div', { class: 'cabecera-reporte' }, tileReporte(reporte, 'grande'),
      el('div', { class: 'titulos' }, el('h1', null, reporte.nombre),
        el('div', { class: 'meta' }, chipEstado(e), el('span', { class: 'chip borde' }, `Versión ${e.version}`), esHerramienta ? null : el('span', { class: 'chip borde' }, icono('i-calendario'), periodoLargo(cierre.periodo)), e.final ? el('span', { class: 'chip acento' }, icono('i-bandera'), 'Resultado final') : null)),
      el('div', { class: 'acciones-fila' }, el('button', { type: 'button', class: 'boton-ayuda-paso', onclick: () => abrirAyuda(PASOS[paso - 1].ayuda) }, icono('i-ayuda'), '¿Cómo sigo?'), enlace('Volver', volver, 'btn fantasma', 'i-volver'))));
    const pasos = el('nav', { class: 'pasos', 'aria-label': 'Pasos del reporte' }, el('div', { class: 'linea' }, el('div', { style: `width:${(paso - 1) * 25}%` })));
    PASOS.forEach((p, i) => {
      const num = i + 1;
      const hecho = num < paso || (num <= 3 && e.estado === 'ok' && num !== paso);
      const habilitado = num !== paso && (num <= 2 || ((num === 3) && (enCurso || terminal)) || ((num === 4 || num === 5) && e.estado === 'ok'));
      pasos.appendChild(el('button', { type: 'button', class: 'paso' + (num === paso ? ' actual' : hecho ? ' hecho' : '') + (habilitado ? ' habilitado' : ''), 'aria-current': num === paso ? 'step' : null, disabled: !habilitado && num !== paso,
        onclick: habilitado ? () => { location.hash = `#/ejecucion/${encodeURIComponent(e.id)}/${num}`; } : null },
        el('span', { class: 'bola' }, icono(hecho ? 'i-check' : p.icono)), el('span', { class: 'nombre-paso' }, p.nombre)));
    });
    main.appendChild(pasos);
    const contenido = el('section', { class: 'tarjeta panel-paso' });
    main.appendChild(contenido);
    await ({ 1: pasoArchivos, 2: pasoOpciones, 3: pasoEjecucion, 4: pasoResultados, 5: pasoExportar }[paso])(contenido, w);
  }
  function intro(iconoNombre, texto) { return el('div', { class: 'intro' }, icono(iconoNombre), el('p', null, texto)); }
  function nuevaVersion(w) {
    return async () => {
      try {
        const e = await api('POST', '/api/ejecuciones', { cierre: w.cierre.id, reporte: w.reporte.codigo });
        await api('PATCH', '/api/ejecuciones/' + encodeURIComponent(e.id), { entradas: w.e.entradas || {}, parametros: w.e.parametros || {} });
        estado.w = null;
        aviso(`Se creó la versión ${e.version}. Revisá las opciones y corré el reporte.`, 'info');
        location.hash = '#/ejecucion/' + encodeURIComponent(e.id) + '/2';
      } catch (err) { avisarError(err); }
    };
  }
  const TIPOS_ARCHIVO = { historico_sga: 'el histórico de cuenta corriente (SGA)', erp_transacciones: 'las transacciones del cliente (ERP)', saldo_comprobacion: 'el saldo de comprobación (ERP)', cheques_sga: 'los cheques (SGA)', tesoreria_erp: 'los valores de tesorería (ERP)', listado_facturas: 'un listado de facturas' };
  const tituloTipo = t => TIPOS_ARCHIVO[t] || t;

  // paso 1
  async function pasoArchivos(cont, w) {
    const { e, reporte } = w;
    let cierre = w.cierre;
    const editable = e.estado === 'borrador' || e.estado === 'listo';
    const seleccion = {};
    for (const ent of reporte.entradas) seleccion[ent.clave] = new Set((e.entradas || {})[ent.clave] || []);
    const recienSubidos = new Set();
    cont.appendChild(intro('i-subir', editable ? 'Elegí los Excel descargados de los sistemas. Si un reporte vino cortado en dos o más archivos, agregalos todos: se leen seguidos, como uno solo.' : 'Estos son los archivos que usó esta versión.'));
    const bloques = el('div');
    const pie = el('div', { class: 'pie-paso' });
    cont.append(bloques, pie);
    const recargar = async () => { cierre = w.cierre = await api('GET', '/api/cierres/' + encodeURIComponent(cierre.id)); pintar(); };
    const subir = async (ent, archivos, barra) => {
      for (const f of archivos) {
        barra.classList.remove('oculto');
        progresoGlobal(1);
        try {
          const a = await subirArchivo(cierre.id, f, p => { barra.firstChild.style.width = Math.round(p * 100) + '%'; });
          recienSubidos.add(a.id);
          if (a.tipo === ent.tipo) { seleccion[ent.clave].add(a.id); aviso(`${a.nombre}: reconocí ${tituloTipo(a.tipo)}` + (a.filas != null ? `, ${n(a.filas)} filas.` : '.'), 'ok'); }
          else if (a.tipo) aviso(`${a.nombre}: reconocí ${tituloTipo(a.tipo)}, que no es lo que pide esta entrada. Quedó guardado en el cierre por si lo necesitás en otro reporte.`, 'atencion', 9000);
          else aviso(`${a.nombre}: ${a.error || 'no reconocí qué reporte es'}.`, 'error', 9000);
          if (a.aviso) aviso(a.aviso, 'atencion', 12000);
        } catch (err) { avisarError(err); }
        finally { progresoGlobal(-1); barra.classList.add('oculto'); barra.firstChild.style.width = '0'; }
      }
      await recargar();
    };
    const desdeCarpeta = async ent => {
      const ruta = await pedirTexto('Tomar archivos de una carpeta', 'Pegá la ruta de la carpeta donde están los Excel (por ejemplo, la de Descargas). Se copian a la herramienta; los originales no se tocan.');
      if (!ruta) return;
      try {
        const lista = await api('POST', `/api/cierres/${encodeURIComponent(cierre.id)}/archivos/carpeta`, { ruta });
        if (!lista.archivos.length) { aviso('En esa carpeta no hay libros de Excel.', 'atencion'); return; }
        const marcas = lista.archivos.map(a => ({ a, casilla: el('input', { type: 'checkbox' }) }));
        const m = abrirModal({ titulo: 'Elegí los archivos', iconoNombre: 'i-carpeta', cuerpo: el('div', null, el('p', { class: 'muted' }, `En ${lista.ruta}. Marcá los que correspondan a ${ent.titulo}.`),
          marcas.map(({ a, casilla }) => el('label', { class: 'archivo' }, casilla, el('span', { class: 'icono-archivo' }, icono('i-planilla')), el('span', { class: 'datos' }, el('span', { class: 'nombre' }, a.nombre), el('span', { class: 'detalle' }, bytesLegibles(a.bytes)))))),
          pie: [btn('Cancelar', () => m.cerrar(), 'fantasma'), btn('Agregar al cierre', async () => {
            const nombres = marcas.filter(x => x.casilla.checked).map(x => x.a.nombre);
            m.cerrar();
            if (!nombres.length) return;
            try {
              progresoGlobal(1);
              const agregados = await api('POST', `/api/cierres/${encodeURIComponent(cierre.id)}/archivos/desde-carpeta`, { ruta, nombres });
              for (const a of agregados) { recienSubidos.add(a.id); if (a.tipo === ent.tipo) seleccion[ent.clave].add(a.id); else aviso(`${a.nombre}: ${a.tipo ? 'reconocí ' + tituloTipo(a.tipo) + ', que no es lo que pide esta entrada' : (a.error || 'no reconocí qué reporte es')}.`, 'atencion', 9000); if (a.aviso) aviso(a.aviso, 'atencion', 12000); }
              await recargar();
            } catch (err) { avisarError(err); } finally { progresoGlobal(-1); }
          }, 'primario', { icono: 'i-check' })] });
      } catch (err) { avisarError(err); }
    };
    const pintar = () => {
      limpiar(bloques);
      for (const ent of reporte.entradas) {
        const sel = seleccion[ent.clave];
        const min = ent.minimo || 1;
        const listo = sel.size >= min;
        const bloque = el('div', { class: 'bloque-entrada' });
        bloque.appendChild(el('div', { class: 'titulo' }, el('h3', null, ent.titulo), listo ? el('span', { class: 'chip ok late' }, icono('i-check'), sel.size === 1 ? 'Listo' : `${sel.size} tramos`) : el('span', { class: 'chip warn' }, icono('i-alerta'), 'Falta elegirlo')));
        if (ent.ayuda) bloque.appendChild(el('div', { class: 'ayuda' }, ent.ayuda));
        const candidatos = cierre.archivos.filter(a => a.tipo === ent.tipo || sel.has(a.id));
        for (const a of candidatos) {
          const detalle = [a.hoja ? `hoja ${a.hoja}` : null, a.filas != null ? `${n(a.filas)} filas` : null, bytesLegibles(a.bytes), 'agregado ' + fechaCorta(a.subido)].filter(Boolean).join(' · ');
          const casilla = el('input', { type: 'checkbox', checked: sel.has(a.id), disabled: !editable, 'aria-label': 'Usar ' + a.nombre, onchange: ev => { if (ev.target.checked) sel.add(a.id); else sel.delete(a.id); pintar(); } });
          bloque.appendChild(el('label', { class: 'archivo' + (sel.has(a.id) ? ' elegido' : '') + (recienSubidos.has(a.id) ? ' nuevo' : '') }, casilla, el('span', { class: 'icono-archivo' }, icono('i-planilla')),
            el('span', { class: 'datos' }, el('span', { class: 'nombre' }, a.nombre), el('span', { class: 'detalle' }, detalle), a.aviso ? el('span', { class: 'detalle aviso' }, a.aviso) : null)));
        }
        if (editable) {
          for (const a of cierre.archivos.filter(x => !x.tipo && recienSubidos.has(x.id))) {
            bloque.appendChild(el('div', { class: 'archivo problema' }, el('span', { class: 'icono-archivo' }, icono('i-alerta')), el('span', { class: 'datos' }, el('span', { class: 'nombre' }, a.nombre), el('span', { class: 'detalle error' }, a.error ? `No se pudo leer: ${a.error}` : 'No reconocí qué reporte es. Revisá que sea el Excel original descargado del sistema.')),
              btn('Quitar', async () => { try { await api('DELETE', `/api/cierres/${encodeURIComponent(cierre.id)}/archivos/${encodeURIComponent(a.id)}`); recienSubidos.delete(a.id); await recargar(); } catch (err) { avisarError(err); } }, 'fantasma chico', { icono: 'i-basura' })));
          }
          const input = el('input', { type: 'file', multiple: true, accept: '.xlsx,.xlsm', 'aria-label': 'Elegir archivos para ' + ent.titulo });
          const barra = el('div', { class: 'barra-subida oculto' }, el('div', { style: 'width:0' }));
          const zona = el('div', { class: 'zona-soltar' }, el('span', { class: 'icono-subir' }, icono('i-subir')),
            el('div', { class: 'texto' }, el('b', null, candidatos.length ? 'Agregar otro archivo o tramo' : 'Arrastrá acá el Excel descargado'), el('span', null, 'o elegilo desde la PC')),
            btn('Elegir archivos', () => input.click(), 'chico', { icono: 'i-archivo' }), btn('Tomar de una carpeta', () => desdeCarpeta(ent), 'fantasma chico', { icono: 'i-carpeta' }), input);
          input.addEventListener('change', () => subir(ent, [...input.files], barra));
          zona.addEventListener('dragover', ev => { ev.preventDefault(); zona.classList.add('sobre'); });
          zona.addEventListener('dragleave', () => zona.classList.remove('sobre'));
          zona.addEventListener('drop', ev => { ev.preventDefault(); zona.classList.remove('sobre'); subir(ent, [...ev.dataTransfer.files], barra); });
          bloque.append(zona, barra);
        }
        bloques.appendChild(bloque);
      }
      const completo = reporte.entradas.every(ent => seleccion[ent.clave].size >= (ent.minimo || 1));
      limpiar(pie);
      if (editable) {
        pie.append(el('div', { class: 'izq' }, el('span', { class: 'muted' }, completo ? 'Todo listo para seguir.' : 'Falta elegir algún archivo.')),
          el('div', { class: 'der' }, btn('Siguiente: opciones', async () => {
            try {
              const entradas = {};
              for (const ent of reporte.entradas) entradas[ent.clave] = [...seleccion[ent.clave]];
              await api('PATCH', '/api/ejecuciones/' + encodeURIComponent(e.id), { entradas });
              estado.w = null;
              location.hash = `#/ejecucion/${encodeURIComponent(e.id)}/2`;
            } catch (err) { avisarError(err); }
          }, 'primario' + (completo ? ' llama' : ''), { icono: 'i-der', disabled: !completo })));
      } else {
        pie.append(el('div', { class: 'izq' }, el('span', { class: 'muted' }, 'Esta versión ya corrió. Para cambiar archivos, creá una versión nueva.')), el('div', { class: 'der' }, btn('Nueva versión con estos datos', nuevaVersion(w), '', { icono: 'i-refrescar' })));
      }
    };
    pintar();
  }
  function subirArchivo(cierreId, archivo, alAvanzar) {
    return new Promise((resolve, reject) => {
      const x = new XMLHttpRequest();
      x.open('POST', `/api/cierres/${encodeURIComponent(cierreId)}/archivos`);
      x.setRequestHeader('X-Nombre', encodeURIComponent(archivo.name));
      x.setRequestHeader('Content-Type', 'application/octet-stream');
      x.upload.onprogress = ev => { if (ev.lengthComputable && alAvanzar) alAvanzar(ev.loaded / ev.total); };
      x.onload = () => {
        let datos = null;
        try { datos = JSON.parse(x.responseText); } catch (err) { /* sin cuerpo */ }
        if (x.status >= 200 && x.status < 300) resolve(datos); else reject(new Error((datos && datos.error) || `No se pudo subir ${archivo.name}.`));
      };
      x.onerror = () => reject(new Error(`No se pudo subir ${archivo.name}.`));
      x.send(archivo);
    });
  }

  // paso 2
  const esPrincipal = p => p.obligatorio || p.tipo === 'fecha' || p.tipo === 'opcion' || (p.tipo === 'lista' && p.opciones);
  async function pasoOpciones(cont, w) {
    const { e, reporte, cierre } = w;
    const editable = e.estado === 'borrador' || e.estado === 'listo';
    const base = await api('GET', `/api/parametros/${reporte.codigo}?cierre=${encodeURIComponent(cierre.id)}`);
    const valores = Object.assign({}, base.valores, Object.keys(e.parametros || {}).length ? e.parametros : {}, w.valores || {});
    w.valores = valores;
    cont.appendChild(intro('i-ajustes', editable ? 'Revisá las opciones de esta corrida. Los valores que ves son los que se usan si no tocás nada: casi siempre alcanza con la fecha de corte y las opciones principales.' : 'Estas son las opciones que usó esta versión.'));
    const propuestas = reporte.codigo === 'controles_sga' ? await reglasPropuestas(cierre.id, e.id) : null;
    const visibles = base.parametros.filter(p => p.clave !== 'sesion_chrome');
    const principales = visibles.filter(esPrincipal);
    const avanzadas = visibles.filter(p => !esPrincipal(p));
    const form = el('form', { onsubmit: ev => ev.preventDefault() });
    if (principales.length) form.appendChild(el('div', { class: 'grupo-opciones' }, principales.map(p => campoParametro(p, valores, editable, propuestas))));
    if (avanzadas.length) {
      form.appendChild(el('details', { class: 'avanzadas', open: !principales.length },
        el('summary', null, icono('i-ajustes'), el('span', null, 'Opciones avanzadas ', el('span', { class: 'muted' }, `(${avanzadas.length}) normalmente no hace falta tocarlas`)), icono('i-abajo', 'flecha')),
        el('div', { class: 'contenido' }, el('div', { class: 'grupo-opciones' }, avanzadas.map(p => campoParametro(p, valores, editable, propuestas))))));
    }
    cont.appendChild(form);
    const guardar = el('input', { type: 'checkbox', id: 'guardar-defaults' });
    const pie = el('div', { class: 'pie-paso' });
    if (editable) {
      pie.append(el('div', { class: 'izq' }, btn('Atrás', () => { location.hash = `#/ejecucion/${encodeURIComponent(e.id)}/1`; }, 'fantasma', { icono: 'i-izq' }),
        visibles.some(p => !p.no_persistir) ? el('label', { class: 'casilla', for: 'guardar-defaults' }, guardar, el('span', null, 'Guardar estos valores para los próximos cierres')) : null),
        el('div', { class: 'der' }, btn('Correr el reporte', async ev => {
          const b = ev.currentTarget;
          b.disabled = true;
          try {
            const r = await api('POST', `/api/ejecuciones/${encodeURIComponent(e.id)}/ejecutar`, { entradas: e.entradas, parametros: valores, guardarDefaults: guardar.checked });
            estado.w.e = r;
            estado.w.valores = null;
            location.hash = `#/ejecucion/${encodeURIComponent(e.id)}/3`;
          } catch (err) { avisarError(err); b.disabled = false; }
        }, 'primario grande llama', { icono: 'i-play' })));
    } else {
      pie.append(el('div', { class: 'izq' }), el('div', { class: 'der' }, btn('Nueva versión con estas opciones', nuevaVersion(w), '', { icono: 'i-refrescar' })));
    }
    cont.appendChild(pie);
  }
  async function reglasPropuestas(cierreId, ejecucionId) {
    try {
      const lista = await api('GET', `/api/ejecuciones?cierre=${encodeURIComponent(cierreId)}&reporte=controles_sga`);
      const ok = lista.filter(x => x.estado === 'ok' && x.id !== ejecucionId && x.resumen && x.resumen.reglas_propuestas);
      if (!ok.length) return null;
      const ultima = ok.sort((a, b) => b.version - a.version)[0];
      return { version: ultima.version, reglas: ultima.resumen.reglas_propuestas };
    } catch (err) { return null; }
  }
  function campoParametro(p, valores, editable, propuestas) {
    const id = 'par-' + p.clave;
    const ancho = p.tipo === 'tabla' || p.tipo === 'lista' || p.tipo === 'opcion';
    const campo = el('div', { class: 'campo' + (ancho ? ' ancho' : '') });
    const v = valores[p.clave];
    const fijar = x => { valores[p.clave] = x; };
    const rotulo = texto => el('div', { class: 'rotulo' }, texto + (p.obligatorio ? ' *' : ''));
    if (p.tipo === 'fecha' || p.tipo === 'texto' || p.tipo === 'ruta' || p.tipo === 'decimal') {
      campo.append(el('label', { for: id }, p.titulo + (p.obligatorio ? ' *' : '')), el('input', { type: p.tipo === 'fecha' ? 'date' : 'text', id, value: v == null ? '' : String(v), disabled: !editable, required: !!p.obligatorio, oninput: ev => fijar(ev.target.value) }));
    } else if (p.tipo === 'opcion') {
      campo.appendChild(rotulo(p.titulo));
      const grupo = el('div', { class: 'opciones-tarjetas', role: 'radiogroup', 'aria-label': p.titulo });
      const pintar = () => {
        limpiar(grupo);
        for (const o of p.opciones) grupo.appendChild(el('label', { class: 'opcion-tarjeta' + (valores[p.clave] === o.valor ? ' elegida' : '') },
          el('input', { type: 'radio', name: id, value: o.valor, checked: valores[p.clave] === o.valor, disabled: !editable, onchange: () => { fijar(o.valor); pintar(); } }), el('span', null, el('b', null, o.titulo))));
      };
      pintar();
      campo.appendChild(grupo);
    } else if (p.tipo === 'booleano') {
      campo.appendChild(el('label', { class: 'casilla', for: id }, el('input', { type: 'checkbox', id, checked: !!v, disabled: !editable, onchange: ev => fijar(ev.target.checked) }), el('span', null, p.titulo)));
    } else if (p.tipo === 'lista' && p.opciones) {
      campo.appendChild(rotulo(p.titulo));
      const actual = new Set(Array.isArray(v) ? v : []);
      campo.appendChild(el('div', { class: 'grupo-opciones' }, p.opciones.map(o => el('label', { class: 'casilla' }, el('input', { type: 'checkbox', checked: actual.has(o.valor), disabled: !editable, onchange: ev => { if (ev.target.checked) actual.add(o.valor); else actual.delete(o.valor); fijar([...actual]); } }), el('span', null, o.titulo)))));
    } else if (p.tipo === 'lista') {
      campo.appendChild(rotulo(p.titulo));
      const items = Array.isArray(v) ? [...v] : [];
      const caja = el('div', { class: 'lista-editable' });
      const pintar = () => {
        limpiar(caja);
        items.forEach((x, i) => caja.appendChild(el('div', { class: 'item' }, el('input', { type: 'text', value: x, disabled: !editable, 'aria-label': `${p.titulo} ${i + 1}`, oninput: ev => { items[i] = ev.target.value; fijar(items.filter(s => s.trim())); } }),
          editable ? el('button', { type: 'button', class: 'btn fantasma icono chico', 'aria-label': 'Quitar', title: 'Quitar', onclick: () => { items.splice(i, 1); fijar(items.filter(s => s.trim())); pintar(); } }, icono('i-x')) : null)));
        if (!items.length) caja.appendChild(el('div', { class: 'item muted' }, 'Vacío'));
        if (editable) caja.appendChild(el('div', { class: 'pie' }, btn('Agregar', () => { items.push(''); pintar(); const ins = caja.querySelectorAll('.item input'); if (ins.length) ins[ins.length - 1].focus(); }, 'chico fantasma', { icono: 'i-mas' })));
      };
      pintar();
      campo.appendChild(caja);
    } else if (p.tipo === 'tabla') {
      campo.appendChild(rotulo(p.titulo));
      const filas = Array.isArray(v) ? v.map(x => ({ ...x })) : [];
      const tabla = el('table', { class: 'tabla-editable' });
      const pintar = () => {
        limpiar(tabla);
        tabla.appendChild(el('thead', null, el('tr', null, p.columnas.map(c => el('th', null, c.titulo)), editable ? el('th', null, '') : null)));
        const cuerpo = el('tbody');
        filas.forEach((f, i) => {
          const tr = el('tr');
          for (const c of p.columnas) {
            let control;
            if (c.tipo === 'booleano') control = el('input', { type: 'checkbox', checked: f[c.clave] === true || f[c.clave] === 'true', disabled: !editable, 'aria-label': c.titulo, onchange: ev => { f[c.clave] = ev.target.checked; fijar(filas); } });
            else if (c.tipo === 'opcion') { control = el('select', { disabled: !editable, 'aria-label': c.titulo, onchange: ev => { f[c.clave] = ev.target.value; fijar(filas); } }); for (const o of c.opciones) control.appendChild(el('option', { value: o, text: o, selected: f[c.clave] === o })); }
            else control = el('input', { type: 'text', value: f[c.clave] == null ? '' : String(f[c.clave]), disabled: !editable, 'aria-label': c.titulo, oninput: ev => { f[c.clave] = ev.target.value; fijar(filas); } });
            tr.appendChild(el('td', null, control));
          }
          if (editable) tr.appendChild(el('td', null, el('button', { type: 'button', class: 'btn fantasma icono chico', 'aria-label': 'Quitar fila', onclick: () => { filas.splice(i, 1); fijar(filas); pintar(); } }, icono('i-x'))));
          cuerpo.appendChild(tr);
        });
        if (!filas.length) cuerpo.appendChild(el('tr', null, el('td', { colspan: String(p.columnas.length + 1), class: 'muted', style: 'padding:10px' }, p.clave === 'reglas' ? 'Sin reglas confirmadas: se usa la propuesta automática del reporte.' : 'Vacío')));
        tabla.appendChild(cuerpo);
      };
      pintar();
      campo.appendChild(tabla);
      if (editable) {
        const acciones = el('div', { class: 'acciones-fila', style: 'margin-top:6px' }, btn('Agregar fila', () => { filas.push({}); fijar(filas); pintar(); }, 'chico fantasma', { icono: 'i-mas' }));
        if (p.clave === 'reglas' && propuestas) acciones.appendChild(btn(`Cargar las reglas propuestas por la versión ${propuestas.version}`, () => {
          const existentes = new Set(filas.map(f => f.concepto));
          for (const [concepto, r] of Object.entries(propuestas.reglas)) {
            if (existentes.has(concepto)) continue;
            filas.push({ concepto, datos: r.datos || 'SIN_DEFINIR', datos_confirmados: !!r.datos_confirmados, agrupador: r.agrupador || '', agrupador_confirmado: !!r.agrupador_confirmado });
          }
          fijar(filas); pintar();
          aviso('Reglas cargadas. Marcá como confirmadas las que valides y corré de nuevo.', 'ok', 9000);
        }, 'chico', { icono: 'i-chispa' }));
        campo.appendChild(acciones);
      }
    }
    if (p.ayuda) campo.appendChild(el('span', { class: 'ayuda' }, p.ayuda));
    return campo;
  }

  // paso 3
  async function pasoEjecucion(cont, w) {
    const { e } = w;
    const iconoEstado = el('div', { class: 'icono-estado girando' }, icono('i-play'));
    const titulo = el('h2', null, 'Corriendo…');
    const pasoActual = el('div', { class: 'paso-actual' });
    const pista = el('div', { class: 'pista indeterminada' }, el('div'));
    const porcentaje = el('span', { class: 'porcentaje' });
    const zonaEspera = el('div');
    const lineaTiempo = el('ol', { class: 'linea-tiempo' });
    const consola = el('div', { class: 'consola', 'aria-live': 'off' });
    const detalle = el('details', { class: 'detalle-tecnico' }, el('summary', null, 'Ver el detalle técnico'), consola);
    const pie = el('div', { class: 'pie-paso' });
    cont.append(el('div', { class: 'estado-ejecucion' }, iconoEstado, el('div', { class: 'textos' }, titulo, pasoActual)), el('div', { class: 'progreso' }, pista, porcentaje), zonaEspera, lineaTiempo, detalle, pie);
    w.nodos = { iconoEstado, titulo, pasoActual, pista, porcentaje, zonaEspera, lineaTiempo, consola, pie };
    if (!e.trabajoId) {
      iconoEstado.className = 'icono-estado' + (e.error ? ' error' : '');
      limpiar(iconoEstado).appendChild(icono(e.error ? 'i-alerta' : 'i-reloj'));
      titulo.textContent = e.error ? 'No se pudo correr' : 'Todavía no corrió';
      pista.parentElement.classList.add('oculto');
      if (e.error) zonaEspera.appendChild(el('div', { class: 'caja-error' }, icono('i-alerta'), el('p', null, e.error)));
      pie.append(el('div', { class: 'izq' }), el('div', { class: 'der' }, btn('Ir a opciones', () => { location.hash = `#/ejecucion/${encodeURIComponent(e.id)}/2`; }, 'primario', { icono: 'i-ajustes' })));
      return;
    }
    const t = await api('GET', '/api/trabajos/' + e.trabajoId);
    pintarTrabajo(t);
    if (t.estado === 'corriendo' || t.estado === 'esperando') {
      estado.sondeo = setInterval(async () => {
        try { const t2 = await api('GET', '/api/trabajos/' + e.trabajoId); pintarTrabajo(t2); if (!(t2.estado === 'corriendo' || t2.estado === 'esperando')) detenerSondeo(); } catch (err) { /* próxima vuelta */ }
      }, 1500);
    }
  }
  function pintarTrabajo(t) {
    const w = estado.w;
    if (!w || !w.nodos || w.paso !== 3) return;
    const anterior = w.trabajo;
    w.trabajo = t;
    const { iconoEstado, titulo, pasoActual, pista, porcentaje, zonaEspera, lineaTiempo, consola, pie } = w.nodos;
    const activo = t.estado === 'corriendo' || t.estado === 'esperando';
    const cambioEstado = !anterior || anterior.estado !== t.estado;
    if (cambioEstado) {
      const ic = { corriendo: 'i-play', esperando: 'i-mano', ok: 'i-check', error: 'i-alerta', cancelado: 'i-detener', interrumpido: 'i-alerta' }[t.estado] || 'i-reloj';
      iconoEstado.className = 'icono-estado ' + ({ corriendo: 'girando', esperando: 'espera', ok: 'ok', error: 'error', interrumpido: 'error' }[t.estado] || '');
      limpiar(iconoEstado).appendChild(icono(ic));
    }
    titulo.textContent = { ok: 'Terminó bien', error: 'Terminó con un error', cancelado: 'Se canceló', interrumpido: 'Se interrumpió', esperando: 'Necesita una acción tuya' }[t.estado] || 'Corriendo…';
    pasoActual.textContent = activo ? (t.paso && t.paso !== 'Arrancando' ? t.paso : 'Preparando…') : t.estado === 'ok' ? 'Los resultados ya están listos para revisar.' : '';
    pista.parentElement.classList.toggle('oculto', !activo && t.estado !== 'ok');
    pista.classList.toggle('indeterminada', activo && !(t.progreso > 0));
    pista.firstChild.style.width = Math.round((t.estado === 'ok' ? 1 : (t.progreso || 0)) * 100) + '%';
    porcentaje.textContent = t.estado === 'ok' ? '100%' : t.progreso > 0 ? Math.round(t.progreso * 100) + '%' : '';
    const lineas = t.lineas || [];
    const pasos = [...new Set(lineas.filter(l => l.startsWith('== ')).map(l => l.slice(3)))];
    limpiar(lineaTiempo);
    pasos.forEach((p, i) => {
      const actual = activo && i === pasos.length - 1;
      lineaTiempo.appendChild(el('li', { class: actual ? 'actual' : 'hecho', style: `animation-delay:${Math.min(i, 6) * .04}s` }, el('span', { class: 'marca-paso' }, actual ? null : icono('i-check')), el('span', null, p)));
    });
    limpiar(consola);
    lineas.slice(-400).forEach((l, i, a) => consola.appendChild(el('div', { class: i === a.length - 1 ? 'ultima' : '' }, l)));
    if (t.error) consola.appendChild(el('div', { class: 'ultima' }, t.error));
    consola.scrollTop = consola.scrollHeight;
    limpiar(zonaEspera);
    if (t.estado === 'esperando' && t.espera) {
      zonaEspera.appendChild(el('div', { class: 'caja-espera' }, icono('i-mano', 'xg'), el('p', null, t.espera.mensaje),
        btn(t.espera.boton || 'Continuar', async ev => { const b = ev.currentTarget; b.disabled = true; try { await api('POST', `/api/trabajos/${t.id}/continuar`, { espera: t.espera.id }); } catch (err) { avisarError(err); b.disabled = false; } }, 'primario grande', { icono: 'i-play' })));
    } else if ((t.estado === 'error' || t.estado === 'interrumpido') && t.error) {
      zonaEspera.appendChild(el('div', { class: 'caja-error' }, icono('i-alerta'), el('div', null, el('p', null, el('b', null, 'Qué pasó: '), t.error), el('p', { class: 'muted' }, 'Corregí lo que indica el mensaje y volvé a correr. Si no se entiende, copiá el detalle técnico para pedir ayuda.'))));
    } else if (t.estado === 'ok') {
      const tablas = Object.entries(t.tablas || {});
      zonaEspera.appendChild(el('div', { class: 'caja-ok' }, icono('i-check-circulo'), el('p', null, tablas.length ? `Se generaron ${tablas.length === 1 ? 'una tabla' : tablas.length + ' tablas'} con ${n(tablas.reduce((s, [, f]) => s + f, 0))} filas para revisar.` : 'El reporte terminó.')));
    }
    limpiar(pie);
    const e = w.e;
    if (activo) {
      pie.append(el('div', { class: 'izq' }, el('span', { class: 'muted' }, 'Podés cerrar esta pestaña: el reporte sigue corriendo.')),
        el('div', { class: 'der' }, btn('Cancelar', async () => { if (await confirmar('¿Cancelar el reporte?', 'Se corta esta corrida. Tus archivos no se tocan y podés volver a correrlo cuando quieras.', 'Cancelar el reporte', 'peligro')) { try { await api('POST', `/api/trabajos/${t.id}/cancelar`, {}); } catch (err) { avisarError(err); } } }, 'peligro', { icono: 'i-detener' })));
    } else if (t.estado === 'ok') {
      pie.append(el('div', { class: 'izq' }), el('div', { class: 'der' }, btn('Revisar los resultados', () => { location.hash = `#/ejecucion/${encodeURIComponent(e.id)}/4`; }, 'primario grande llama', { icono: 'i-tabla' })));
    } else {
      pie.append(el('div', { class: 'izq' }, btn('Ver el registro completo', async () => {
        try { const r = await api('GET', `/api/ejecuciones/${encodeURIComponent(e.id)}/registro`); abrirModal({ titulo: 'Registro de la corrida', iconoNombre: 'i-archivo', ancho: true, cuerpo: el('div', { class: 'consola', style: 'max-height:60vh' }, r.registro || 'Vacío') }); } catch (err) { avisarError(err); }
      }, 'fantasma', { icono: 'i-archivo' })), el('div', { class: 'der' }, btn('Corregir y volver a correr', nuevaVersion(w), 'primario', { icono: 'i-refrescar' })));
    }
  }

  // paso 4
  async function pasoResultados(cont, w) {
    const { e } = w;
    const datos = await api('GET', `/api/ejecuciones/${encodeURIComponent(e.id)}/tablas`);
    w.tablas = datos.tablas;
    if (!datos.tablas.length) { cont.appendChild(intro('i-info', 'El reporte terminó pero no dejó tablas para revisar. Sus archivos están en el paso Exportar.')); return; }
    const revisables = () => w.tablas.filter(t => t.revisable !== false);
    if (!w.tabla || !datos.tablas.some(t => t.tabla === w.tabla)) w.tabla = (datos.tablas.find(t => t.principal) || revisables().find(t => t.estados.pendiente > 0) || datos.tablas[0]).tabla;
    const medidor = el('div', { class: 'tarjeta resumen-revision' });
    const pintarMedidor = () => {
      const tot = revisables().reduce((a, t) => ({ p: a.p + t.estados.pendiente, r: a.r + t.estados.revisada, o: a.o + t.estados.omitida }), { p: 0, r: 0, o: 0 });
      const total = tot.p + tot.r + tot.o;
      if (!revisables().length) {
        limpiar(medidor).append(el('span', { class: 'tile', style: 'background:var(--accent-suave);color:var(--accent)' }, icono('i-info')),
          el('div', { class: 'medidor' }, el('b', null, 'Este reporte no tiene filas para revisar una por una'), el('div', { class: 'muted' }, 'Es un control de totales: el resultado está en la tabla de la izquierda.')),
          el('div', { class: 'acciones-fila' }, btn('Exportar', () => { location.hash = `#/ejecucion/${encodeURIComponent(e.id)}/5`; }, 'chico', { icono: 'i-bajar' })));
        return tot;
      }
      const pct = total ? Math.round((tot.r + tot.o) / total * 100) : 100;
      limpiar(medidor).append(el('div', { class: 'cifra' }, `${pct}%`, el('br'), el('small', null, 'revisado')),
        el('div', { class: 'medidor' }, el('b', null, tot.p ? `Te faltan ${n(tot.p)} filas por revisar` : 'Revisaste todo'), barraRevision({ pendientes: tot.p, revisadas: tot.r, omitidas: tot.o }),
          el('div', { class: 'leyenda-revision' }, el('span', null, el('b', null, n(tot.r)), ' revisadas'), el('span', null, el('b', null, n(tot.o)), ' omitidas'), el('span', null, el('b', null, n(tot.p)), ' pendientes'))),
        el('div', { class: 'acciones-fila' }, btn('Traer la revisión del cierre anterior', traerAnterior, 'fantasma chico', { icono: 'i-deshacer' }), btn('Exportar', () => { location.hash = `#/ejecucion/${encodeURIComponent(e.id)}/5`; }, 'chico', { icono: 'i-bajar' })));
      return tot;
    };
    const traerAnterior = async () => {
      if (!await confirmar('¿Traer la revisión del cierre anterior?', 'Se marcan como omitidas, con su observación, las filas que en el cierre anterior se omitieron y que acá siguen pendientes. Las revisadas no se traen: son de ese mes.', 'Traer', 'pregunta')) return;
      try { const r = await api('POST', `/api/ejecuciones/${encodeURIComponent(e.id)}/traer-revision-anterior`, {}); aviso(r.desde ? `Del cierre de ${periodoLargo(r.desde)}: ${n(r.aplicadas)} filas marcadas${r.sin_destino ? `, ${n(r.sin_destino)} sin fila en este mes` : ''}.` : 'No hay un cierre anterior con este reporte.', r.desde ? 'ok' : 'atencion'); await pasoResultados(limpiar(cont), w); } catch (err) { avisarError(err); }
    };
    cont.appendChild(intro('i-tabla', 'Marcá cada fila como revisada u omitida y anotá observaciones. Lo que marques se guarda solo y pasa a la próxima versión de este mes.'));
    if (datos.traslado && datos.traslado.desde) cont.appendChild(el('div', { class: 'caja-info', style: 'margin:0 0 14px' }, icono('i-deshacer'), el('p', null, `De la versión ${datos.traslado.desde} se trasladaron ${n(datos.traslado.aplicadas)} marcas` + (datos.traslado.sin_destino ? `; ${n(datos.traslado.sin_destino)} no encontraron su fila en esta versión.` : '.'))));
    cont.appendChild(medidor);
    pintarMedidor();
    if (datos.resumen && typeof datos.resumen === 'object') {
      const grilla = el('div', { class: 'tarjeta resumen-motor' });
      for (const [k, v] of Object.entries(datos.resumen)) {
        if (v && typeof v === 'object' && !Array.isArray(v)) { for (const [k2, v2] of Object.entries(v)) if (typeof v2 !== 'object' || v2 === null) grilla.appendChild(el('div', null, el('span', null, `${k} · ${k2}`), el('span', { title: String(v2) }, String(v2)))); }
        else if (!Array.isArray(v)) grilla.appendChild(el('div', null, el('span', null, k), el('span', { title: String(v) }, String(v))));
      }
      cont.appendChild(el('details', { class: 'resumen-corrida' }, el('summary', null, icono('i-info'), 'Resumen de la corrida', icono('i-abajo', 'flecha')), grilla));
    }
    const cuerpo = el('div', { class: 'resultados' });
    const lista = el('nav', { class: 'tarjeta lista-tablas', 'aria-label': 'Tablas del reporte' });
    const derecha = el('div');
    cuerpo.append(lista, derecha);
    cont.appendChild(cuerpo);
    const pintarLista = () => {
      limpiar(lista);
      const libros = new Set(w.tablas.map(t => t.archivo).filter(Boolean));
      const boton = t => {
        const varios = libros.size > 1 && t.archivo && w.tablas.filter(x => x.archivo === t.archivo).length > 1;
        return el('button', { type: 'button', class: t.tabla === w.tabla ? 'activa' : '', 'aria-current': t.tabla === w.tabla ? 'true' : null,
          onclick: () => { w.tabla = t.tabla; w.grilla.desde = 0; w.grilla.seleccion.clear(); pintarLista(); grilla(derecha, w, alCambiar); } },
          icono(t.revisable === false ? 'i-info' : 'i-tabla'), el('span', { class: 'nombre' }, varios && t.hoja ? t.hoja : t.titulo),
          t.revisable === false ? el('span', { class: 'muted', style: 'font-size:12px' }, n(t.filas)) :
            el('span', { class: 'pend' + (t.estados.pendiente ? '' : ' cero'), title: `${n(t.estados.pendiente)} pendientes de ${n(t.filas)}` }, t.estados.pendiente ? n(t.estados.pendiente) : '✓'));
      };
      let libro = null;
      for (const t of revisables()) {
        const varios = libros.size > 1 && t.archivo && w.tablas.filter(x => x.archivo === t.archivo).length > 1;
        if (varios && t.archivo !== libro) { libro = t.archivo; lista.appendChild(el('div', { class: 'libro' }, t.archivo.replace(/\.(xlsx|csv|txt)$/i, '').replace(/_/g, ' '))); }
        lista.appendChild(boton(t));
      }
      const info = w.tablas.filter(t => t.revisable === false);
      if (info.length) {
        lista.appendChild(el('div', { class: 'libro' }, 'Información'));
        for (const t of info) lista.appendChild(boton(t));
      }
    };
    let todoRevisado = revisables().every(t => !t.estados.pendiente);
    const alCambiar = () => {
      pintarLista();
      const tot = pintarMedidor();
      if (!todoRevisado && tot.p === 0 && revisables().length) { todoRevisado = true; fiesta(); aviso('Revisaste todas las filas. Podés exportar el Excel trabajado y marcar esta versión como resultado final.', 'ok', 8000); }
      else if (tot.p > 0) todoRevisado = false;
    };
    pintarLista();
    await grilla(derecha, w, alCambiar);
  }
  const TONO_RESULTADO = [[/^(COINCIDE|OK)/, 'ok'], [/DIFERENCIA|ERROR|FALTANTE|DUPLICADO/, 'error'], [/REVISAR|SOLO|SIN |PENDIENTE|FUERA|ANULADA/, 'warn']];
  function celdaResultado(v) {
    const par = TONO_RESULTADO.find(([re]) => re.test(v || ''));
    return el('span', { class: 'chip ' + (par ? par[1] : '') }, el('span', { class: 'punto' }), v);
  }
  async function grilla(cont, w, alCambiar) {
    const g = w.grilla;
    const e = w.e;
    const info = w.tablas.find(t => t.tabla === w.tabla);
    const revisable = info.revisable !== false;
    if (!revisable) g.estado = '';
    limpiar(cont);
    const buscar = el('input', { type: 'search', placeholder: 'Buscar en esta tabla…', value: g.filtro, 'aria-label': 'Buscar' });
    let temporizador = null;
    buscar.addEventListener('input', () => { clearTimeout(temporizador); temporizador = setTimeout(() => { g.filtro = buscar.value; g.desde = 0; cargar(); }, 350); });
    const columna = el('select', { class: 'selector', 'aria-label': 'Buscar sólo en una columna', onchange: ev => { g.columna = ev.target.value; if (g.filtro) { g.desde = 0; cargar(); } } },
      el('option', { value: '', text: 'En todas las columnas' }), info.columnas.map(c => el('option', { value: c, text: c, selected: g.columna === c })));
    const filtros = el('div', { class: 'segmentado', role: 'group', 'aria-label': 'Filtrar por revisión' });
    const ESTADOS_FILTRO = [['', 'Todas'], ['pendiente', 'Pendientes'], ['revisada', 'Revisadas'], ['omitida', 'Omitidas']];
    for (const [valor, texto] of ESTADOS_FILTRO) filtros.appendChild(el('button', { type: 'button', 'data-valor': valor, class: g.estado === valor ? 'activa' : '', onclick: () => { g.estado = valor; g.desde = 0; g.seleccion.clear(); cargar(); } }, texto));
    const cantidad = el('select', { class: 'selector', 'aria-label': 'Filas por página', onchange: ev => { g.cantidad = parseInt(ev.target.value, 10); g.desde = 0; cargar(); } }, [100, 250, 500].map(c => el('option', { value: String(c), text: c + ' por página', selected: g.cantidad === c })));
    cont.appendChild(el('div', { class: 'barra-grilla' }, el('div', { class: 'buscador' }, icono('i-buscar'), buscar), columna, revisable ? filtros : null, cantidad));
    const acciones = el('div', { class: 'barra-seleccion vacia' });
    const marco = el('div', { class: 'marco-grilla' });
    const pie = el('div', { class: 'paginado' });
    cont.append(acciones, marco, pie);
    let pagina = null;
    const marcar = async (filas, estadoNuevo, obs) => {
      if (!filas.length) return;
      try {
        const r = await api('POST', `/api/ejecuciones/${encodeURIComponent(e.id)}/triage`, { tabla: w.tabla, filas, estado: estadoNuevo, obs });
        for (const t of w.tablas) if (r.estados[t.tabla]) t.estados = r.estados[t.tabla];
        const cambiadas = new Set(filas);
        g.seleccion.clear();
        alCambiar();
        await cargar(cambiadas);
        const texto = estadoNuevo === 'revisada' ? 'marcadas como revisadas' : estadoNuevo === 'omitida' ? 'omitidas' : estadoNuevo === 'pendiente' ? 'vueltas a pendiente' : 'con la observación guardada';
        aviso(`${filas.length === 1 ? 'Una fila' : n(filas.length) + ' filas'} ${texto}.`, 'ok', 2600);
      } catch (err) { avisarError(err); }
    };
    const pintarAcciones = () => {
      limpiar(acciones);
      const cuantas = g.seleccion.size;
      acciones.classList.toggle('vacia', cuantas === 0);
      if (!revisable) { acciones.append(icono('i-info'), el('span', null, 'Tabla informativa: muestra totales o datos de respaldo y no se revisa fila por fila.')); return; }
      if (!cuantas) { acciones.append(icono('i-info'), el('span', null, 'Hacé clic en una o más filas para marcarlas como revisadas u omitidas, o para anotarles una observación. Doble clic en Observaciones edita una sola fila.')); return; }
      const filas = [...g.seleccion];
      const obs = el('input', { type: 'text', class: 'entrada-texto', placeholder: 'Observación (opcional)…', 'aria-label': 'Observación' });
      acciones.append(el('span', { class: 'cuenta-sel' }, cuantas === 1 ? '1 fila' : `${n(cuantas)} filas`),
        btn('Revisada', () => marcar(filas, 'revisada', obs.value || null), 'chico', { icono: 'i-check' }),
        btn('Omitir', () => marcar(filas, 'omitida', obs.value || null), 'chico', { icono: 'i-ojo-tachado' }),
        btn('Pendiente', () => marcar(filas, 'pendiente', obs.value || null), 'chico fantasma', { icono: 'i-deshacer' }),
        obs, btn('Guardar observación', () => marcar(filas, null, obs.value), 'chico primario', { icono: 'i-mensaje' }),
        btn('', () => { g.seleccion.clear(); pintarAcciones(); pintarTabla(); }, 'fantasma icono chico', { icono: 'i-x', aria: 'Deseleccionar', title: 'Deseleccionar' }));
    };
    const pintarTabla = (cambiadas = new Set()) => {
      limpiar(marco);
      if (!pagina) return;
      const tabla = el('table', { class: 'grilla' });
      const todas = el('input', { type: 'checkbox', 'aria-label': 'Marcar todas las filas de la página', checked: pagina.filas.length > 0 && pagina.filas.every(f => g.seleccion.has(f._fila)),
        onchange: ev => { for (const f of pagina.filas) { if (ev.target.checked) g.seleccion.add(f._fila); else g.seleccion.delete(f._fila); } pintarAcciones(); pintarTabla(); } });
      const th = c => {
        const activa = g.orden === c;
        const num = pagina.tipos[pagina.columnas.indexOf(c)] === 'numero';
        return el('th', { class: num ? 'num' : '', 'aria-sort': activa ? (g.desc ? 'descending' : 'ascending') : null },
          el('button', { type: 'button', title: 'Ordenar por ' + c, onclick: () => { if (activa && !g.desc) g.desc = true; else if (activa && g.desc) { g.orden = null; g.desc = false; } else { g.orden = c; g.desc = false; } g.desde = 0; cargar(); } },
            c, activa ? (() => { const ic = icono('i-abajo'); if (!g.desc) ic.style.transform = 'rotate(180deg)'; return ic; })() : null));
      };
      tabla.appendChild(el('thead', null, el('tr', null, revisable ? [el('th', { class: 'sel' }, todas), el('th', null, el('button', { type: 'button', onclick: () => { g.orden = g.orden === '_estado' ? null : '_estado'; g.desde = 0; cargar(); } }, 'Revisión'))] : null, pagina.columnas.map(th), revisable ? el('th', null, 'Observaciones') : null)));
      const cuerpo = el('tbody');
      for (const f of pagina.filas) {
        const tr = el('tr', { class: (g.seleccion.has(f._fila) ? 'seleccionada ' : '') + f._estado + (cambiadas.has(f._fila) ? ' cambio' : '') });
        const casilla = el('input', { type: 'checkbox', checked: g.seleccion.has(f._fila), 'aria-label': 'Marcar fila', onchange: ev => { if (ev.target.checked) g.seleccion.add(f._fila); else g.seleccion.delete(f._fila); tr.classList.toggle('seleccionada', ev.target.checked); pintarAcciones(); } });
        if (revisable) tr.appendChild(el('td', { class: 'sel' }, casilla));
        const origen = f._origen && f._origen !== 'manual' && f._estado !== 'pendiente' ? { version: 'de la versión anterior', cierre: 'del cierre anterior', importado: 'importada' }[f._origen] : null;
        if (revisable) tr.appendChild(el('td', { class: 'revision', title: origen ? 'Marca ' + origen : null },
          f._estado === 'revisada' ? el('span', { class: 'chip ok' }, icono('i-check'), 'Revisada') : f._estado === 'omitida' ? el('span', { class: 'chip' }, icono('i-ojo-tachado'), 'Omitida') : el('span', { class: 'chip borde' }, 'Pendiente')));
        f.valores.forEach((v, i) => {
          const nombre = pagina.columnas[i];
          const num = pagina.tipos[i] === 'numero';
          const contenido = (nombre === 'Resultado' || nombre === 'Estado') && v ? celdaResultado(v) : num ? numeroLegible(v) : v;
          tr.appendChild(el('td', { class: (num ? 'num' : '') + (f._marcas.includes(nombre) ? ' resaltada' : ''), title: v && v.length > 36 ? v : null }, contenido));
        });
        if (!revisable) { tr.style.cursor = 'default'; cuerpo.appendChild(tr); continue; }
        tr.appendChild(el('td', { class: 'obs', title: f._obs ? f._obs : 'Doble clic para escribir una observación' }, f._obs || ''));
        tr.addEventListener('click', ev => { if (ev.target.closest('input,button')) return; casilla.checked = !casilla.checked; casilla.dispatchEvent(new Event('change')); });
        tr.lastChild.addEventListener('dblclick', async ev => {
          ev.stopPropagation();
          const t = await pedirTexto('Observación', 'Lo que quieras anotar sobre esta fila.', f._obs || '', true);
          if (t === null) return;
          await marcar([f._fila], null, t);
        });
        cuerpo.appendChild(tr);
      }
      if (!pagina.filas.length) cuerpo.appendChild(el('tr', null, el('td', { colspan: String(pagina.columnas.length + (revisable ? 3 : 0)), class: 'vacia' }, g.filtro || g.estado ? 'Ninguna fila coincide con el filtro.' : 'Esta tabla está vacía: no hay nada para revisar.')));
      tabla.appendChild(cuerpo);
      marco.appendChild(tabla);
      limpiar(pie);
      const desde = pagina.total ? g.desde + 1 : 0;
      const hasta = Math.min(g.desde + g.cantidad, pagina.total);
      pie.append(el('span', null, `Filas ${n(desde)} a ${n(hasta)} de ${n(pagina.total)}`),
        el('div', { class: 'botones' }, btn('Anterior', () => { g.desde = Math.max(0, g.desde - g.cantidad); cargar(); }, 'chico', { icono: 'i-izq', disabled: g.desde === 0 }), btn('Siguiente', () => { g.desde += g.cantidad; cargar(); }, 'chico', { icono: 'i-der', disabled: hasta >= pagina.total })));
    };
    const cargar = async (cambiadas) => {
      const q = new URLSearchParams({ desde: g.desde, cantidad: g.cantidad, filtro: g.filtro, estado: g.estado, columna: g.columna });
      if (g.orden) { q.set('orden', g.orden); q.set('desc', g.desc ? '1' : '0'); }
      try { pagina = await api('GET', `/api/ejecuciones/${encodeURIComponent(e.id)}/tablas/${w.tabla}?${q}`); } catch (err) { avisarError(err); return; }
      for (const b of filtros.children) b.classList.toggle('activa', b.dataset.valor === g.estado);
      pintarAcciones();
      pintarTabla(cambiadas instanceof Set ? cambiadas : new Set());
    };
    await cargar();
  }

  // paso 5
  async function pasoExportar(cont, w) {
    const { e, reporte, cierre } = w;
    const [archivos, datos] = await Promise.all([api('GET', `/api/ejecuciones/${encodeURIComponent(e.id)}/archivos`), api('GET', `/api/ejecuciones/${encodeURIComponent(e.id)}/tablas`)]);
    const base = `/api/ejecuciones/${encodeURIComponent(e.id)}`;
    const sinOmitidas = el('input', { type: 'checkbox', id: 'sin-omitidas' });
    const libros = [...new Set(datos.tablas.map(t => t.archivo).filter(Boolean))];
    const listaTrabajados = el('div', { class: 'lista-descargas' });
    const pintar = () => {
      limpiar(listaTrabajados);
      const suf = sinOmitidas.checked ? '&incluirOmitidas=0' : '';
      for (const libro of libros) listaTrabajados.appendChild(el('a', { class: 'descarga', href: `${base}/exportar?libro=${encodeURIComponent(libro)}${suf}` }, el('span', { class: 'icono-archivo' }, icono('i-planilla', 'g')),
        el('span', { class: 'datos' }, el('b', null, libros.length === 1 ? reporte.nombre : libro.replace(/\.(xlsx|csv|txt)$/i, '').replace(/_/g, ' ')), el('small', null, 'Excel trabajado · ' + datos.tablas.filter(t => t.archivo === libro).map(t => t.hoja || t.titulo).join(', '))), icono('i-bajar')));
    };
    sinOmitidas.addEventListener('change', pintar);
    pintar();
    const listaOriginales = el('div', { class: 'lista-descargas' });
    for (const a of archivos) listaOriginales.appendChild(el('a', { class: 'descarga', href: `${base}/archivos/${a.ruta.split('/').map(encodeURIComponent).join('/')}` }, el('span', { class: 'icono-archivo', style: 'background:var(--panel2);color:var(--muted)' }, icono('i-archivo', 'g')), el('span', { class: 'datos' }, el('b', null, a.ruta), el('small', null, bytesLegibles(a.bytes))), icono('i-bajar')));
    if (!archivos.length) listaOriginales.appendChild(el('p', { class: 'muted' }, 'Esta corrida no dejó archivos.'));
    const final = el('input', { type: 'checkbox', checked: !!e.final, onchange: async ev => {
      try {
        const r = await api('PATCH', base, { final: ev.target.checked });
        w.e = r;
        if (r.final) { fiesta(); aviso(`Listo: esta versión es el resultado final de ${reporte.nombre}.`, 'ok'); } else aviso('Ya no es el resultado final.', 'info');
      } catch (err) { avisarError(err); ev.target.checked = !ev.target.checked; }
    } });
    cont.append(intro('i-bajar', 'Descargá el Excel trabajado: el mismo del reporte, con las columnas Estado revisión y Observaciones completas con lo que marcaste.'),
      el('div', { class: 'grilla-2' },
        el('div', null, el('div', { class: 'titulo-seccion', style: 'margin-top:0' }, icono('i-check-circulo'), el('h2', null, 'Resultados trabajados')),
          el('label', { class: 'casilla', for: 'sin-omitidas', style: 'margin-bottom:8px' }, sinOmitidas, el('span', null, 'Sin las filas omitidas')), listaTrabajados),
        el('div', null, el('div', { class: 'titulo-seccion', style: 'margin-top:0' }, icono('i-archivo'), el('h2', null, 'Archivos originales')), el('p', { class: 'muted' }, 'Tal como los produce el reporte, sin tocar.'), listaOriginales)),
      el('div', { class: 'pie-paso' },
        el('label', { class: 'interruptor' }, final, el('span', { class: 'riel' }), el('span', null, el('b', null, 'Resultado final'), el('br'), el('span', { class: 'muted' }, `Esta versión es la que vale para ${cierre.herramienta ? 'el registro' : 'el cierre de ' + periodoLargo(cierre.periodo).toLowerCase()}.`))),
        el('div', { class: 'der' }, cierre.herramienta ? null : el('a', { class: 'btn fantasma', href: `/api/cierres/${encodeURIComponent(cierre.id)}/exportar` }, icono('i-caja'), el('span', null, 'Exportar el cierre completo')),
          btn('Nueva versión', nuevaVersion(w), 'fantasma', { icono: 'i-refrescar' }), enlace(cierre.herramienta ? 'Volver a Facturas' : 'Volver al cierre', cierre.herramienta ? '#/facturas' : '#/cierre/' + encodeURIComponent(cierre.id), 'btn primario', 'i-volver'))));
  }

  // ---------------------------------------------------------------- vista: historial
  function tablaEjecuciones(lista, { mostrarCierre = true, periodos = {}, alBorrar = null } = {}) {
    const nombres = Object.fromEntries(estado.app.reportes.map(r => [r.codigo, r]));
    const tabla = el('table', { class: 'tabla-simple' }, el('thead', null, el('tr', null, ['Reporte', mostrarCierre ? 'Cierre' : null, 'Versión', 'Fecha', 'Estado', 'Revisión', ''].filter(x => x !== null).map(t => el('th', null, t)))));
    const cuerpo = el('tbody');
    for (const x of lista) {
      const r = nombres[x.reporte] || { codigo: x.reporte, nombre: x.reporte, icono: 'reporte' };
      const acciones = [{ icono: 'i-der', texto: 'Abrir', onclick: () => { location.hash = '#/ejecucion/' + encodeURIComponent(x.id); } }, 'sep',
        { icono: 'i-basura', texto: 'Borrar esta versión', peligro: true, onclick: async () => {
          if (!await confirmar('¿Borrar esta versión?', (x.final ? 'Es el resultado final. ' : '') + 'Se pierden sus resultados y su revisión. No se puede deshacer.', 'Borrar', 'peligro')) return;
          try { await api('DELETE', `/api/ejecuciones/${encodeURIComponent(x.id)}?forzar=1`); aviso('Versión borrada.', 'ok'); if (alBorrar) alBorrar(x); else enrutar(); } catch (err) { avisarError(err); }
        } }];
      const fila = el('tr', null,
        el('td', null, el('a', { class: 'celda-reporte', href: '#/ejecucion/' + encodeURIComponent(x.id), style: 'color:inherit;text-decoration:none' }, tileReporte(r), el('b', null, r.nombre))),
        mostrarCierre ? el('td', null, periodos[x.cierreId] ? periodoLargo(periodos[x.cierreId]) : el('span', { class: 'muted' }, 'Facturas')) : null,
        el('td', null, el('span', { class: 'chip borde' }, `Versión ${x.version}`), x.final ? el('span', { class: 'chip acento', style: 'margin-left:6px' }, icono('i-bandera'), 'Final') : null),
        el('td', null, fechaCorta(x.fin || x.inicio || x.creado)),
        el('td', null, chipEstado(x)),
        el('td', { style: 'min-width:160px' }, x.estado === 'ok' ? [barraRevision(x.revision), el('div', { class: 'leyenda-revision', style: 'margin-top:4px' }, el('span', null, el('b', null, n(x.revision.pendientes)), ' pendientes'))] : el('span', { class: 'muted' }, '—')),
        el('td', { style: 'text-align:right' }, botonMenu(acciones, 'Acciones de la versión')));
      cuerpo.appendChild(fila);
    }
    tabla.appendChild(cuerpo);
    return el('div', { class: 'tarjeta entrar', style: 'overflow:visible' }, tabla);
  }
  async function vistaHistorial() {
    const sello = nuevoSello();
    estado.w = null;
    const partes = estado.vista.partes;
    const [ejecuciones, cierres, app] = await Promise.all([api('GET', '/api/ejecuciones'), api('GET', '/api/cierres'), api('GET', '/api/estado')]);
    if (!vigente(sello)) return;
    estado.app = app;
    const main = limpiar($('#vista'));
    const periodos = Object.fromEntries(cierres.map(c => [c.id, c.periodo]));
    const filtro = { cierre: partes[1] || '', reporte: partes[2] || '', estado: '' };
    main.appendChild(el('div', { class: 'encabezado entrar' }, el('div', null, el('h1', null, 'Historial'), el('div', { class: 'sub' }, 'Todas las corridas, de todos los cierres. Las versiones viejas se pueden borrar desde el menú de cada fila.'))));
    const selCierre = el('select', { class: 'selector', 'aria-label': 'Cierre', onchange: ev => { filtro.cierre = ev.target.value; pintar(); } }, el('option', { value: '', text: 'Todos los cierres' }), cierres.map(c => el('option', { value: c.id, text: periodoLargo(c.periodo), selected: filtro.cierre === c.id })));
    const selReporte = el('select', { class: 'selector', 'aria-label': 'Reporte', onchange: ev => { filtro.reporte = ev.target.value; pintar(); } }, el('option', { value: '', text: 'Todos los reportes' }), app.reportes.map(r => el('option', { value: r.codigo, text: r.nombre, selected: filtro.reporte === r.codigo })));
    const selEstado = el('select', { class: 'selector', 'aria-label': 'Estado', onchange: ev => { filtro.estado = ev.target.value; pintar(); } }, el('option', { value: '', text: 'Cualquier estado' }), Object.entries(ESTADO_TEXTO).map(([v, t]) => el('option', { value: v, text: t })));
    main.appendChild(el('div', { class: 'barra-grilla entrar' }, icono('i-filtro'), selCierre, selReporte, selEstado));
    const marco = el('div');
    main.appendChild(marco);
    const pintar = () => {
      limpiar(marco);
      const lista = ejecuciones.filter(x => (!filtro.cierre || x.cierreId === filtro.cierre) && (!filtro.reporte || x.reporte === filtro.reporte) && (!filtro.estado || x.estado === filtro.estado));
      if (!lista.length) { marco.appendChild(el('div', { class: 'vacio' }, el('div', { class: 'ilustracion' }, icono('i-historial')), el('h2', null, ejecuciones.length ? 'No hay corridas con ese filtro' : 'Todavía no hay corridas'), el('p', null, 'Cada vez que corras un reporte, la versión va a quedar registrada acá.'))); return; }
      marco.appendChild(tablaEjecuciones(lista, { periodos, alBorrar: x => { ejecuciones.splice(ejecuciones.indexOf(x), 1); pintar(); } }));
    };
    pintar();
  }

  // ---------------------------------------------------------------- vista: configuración
  async function vistaConfiguracion() {
    const sello = nuevoSello();
    estado.w = null;
    const [conf, app] = await Promise.all([api('GET', '/api/configuracion'), api('GET', '/api/estado')]);
    if (!vigente(sello)) return;
    estado.app = app;
    estado.conf = conf;
    const main = limpiar($('#vista'));
    const seccion = (iconoNombre, titulo, texto, ...contenido) => el('section', { class: 'tarjeta seccion-config' }, el('div', { class: 'cabeza' }, el('span', { class: 'tile' }, icono(iconoNombre)), el('div', null, el('h2', null, titulo), texto ? el('div', { class: 'muted' }, texto) : null)), contenido);
    const temaSeg = el('div', { class: 'segmentado', role: 'group', 'aria-label': 'Tema' });
    for (const [v, t, ic] of [['claro', 'Claro', 'i-sol'], ['oscuro', 'Oscuro', 'i-luna']]) {
      temaSeg.appendChild(el('button', { type: 'button', 'data-valor': v, class: document.documentElement.dataset.tema === v ? 'activa' : '', onclick: async () => {
        aplicarTema(v); for (const b of temaSeg.children) b.classList.toggle('activa', b.dataset.valor === v);
        try { await api('PATCH', '/api/configuracion', { tema: v }); } catch (err) { /* queda local */ }
      } }, icono(ic), t));
    }
    const limite = el('input', { type: 'number', min: '10', max: '2000', value: String(conf.limiteMB), id: 'limite', style: 'max-width:150px' });
    const selReporte = el('select', { class: 'selector', 'aria-label': 'Reporte' }, app.reportes.map(r => el('option', { value: r.codigo, text: r.nombre })));
    const formDefaults = el('div');
    const pintarDefaults = async () => {
      limpiar(formDefaults);
      const codigo = selReporte.value;
      const base = await api('GET', `/api/parametros/${codigo}`);
      const valores = Object.assign({}, base.valores);
      const persistibles = base.parametros.filter(p => !p.no_persistir && p.clave !== 'sesion_chrome');
      if (!persistibles.length) { formDefaults.appendChild(el('p', { class: 'muted' }, 'Este reporte no tiene valores para guardar.')); return; }
      formDefaults.appendChild(el('div', { class: 'grupo-opciones' }, persistibles.map(p => campoParametro(p, valores, true, null))));
      formDefaults.appendChild(btn('Guardar como valores por defecto', async () => {
        try { const datos = {}; for (const p of persistibles) datos[p.clave] = valores[p.clave]; await api('PATCH', '/api/configuracion', { reportes: { [codigo]: { parametros: datos } } }); aviso('Valores guardados. Se usan en los próximos cierres.', 'ok'); } catch (err) { avisarError(err); }
      }, 'primario', { icono: 'i-check' }));
    };
    selReporte.addEventListener('change', () => pintarDefaults().catch(avisarError));
    main.append(el('div', { class: 'encabezado entrar' }, el('div', null, el('h1', null, 'Configuración'), el('div', { class: 'sub' }, 'Apariencia, valores por defecto de cada reporte y datos de la herramienta.'))),
      el('div', { class: 'escalonado' },
        seccion('i-sol', 'Apariencia', 'El tema claro es el predeterminado.', el('div', { class: 'campo' }, el('div', { class: 'rotulo' }, 'Tema'), temaSeg)),
        seccion('i-archivo', 'Archivos', 'Los reportes históricos suelen pesar entre 50 y 100 MB.', el('div', { class: 'campo' }, el('label', { for: 'limite' }, 'Tamaño máximo de cada archivo (MB)'), limite),
          btn('Guardar', async () => { try { await api('PATCH', '/api/configuracion', { limiteMB: parseInt(limite.value, 10) }); aviso('Guardado.', 'ok'); } catch (err) { avisarError(err); } }, 'chico', { icono: 'i-check' })),
        seccion('i-ajustes', 'Valores por defecto de cada reporte', 'Lo que guardes acá aparece ya cargado en el paso Opciones. En cada corrida se puede cambiar igual.', el('div', { class: 'campo', style: 'max-width:340px' }, el('div', { class: 'rotulo' }, 'Reporte'), selReporte), formDefaults),
        seccion('i-carpeta', 'Dónde están los datos', 'Los cierres, los archivos agregados, los resultados y las revisiones se guardan en esta carpeta de tu PC. No la compartas ni la pongas en OneDrive: para mandar un cierre usá "Exportar el cierre".',
          el('p', null, el('code', null, conf.carpetaDatos)),
          btn('Liberar espacio', async () => {
            if (!await confirmar('¿Liberar espacio?', 'Se borran los Excel agregados que ninguna versión final usa. Los resultados y las revisiones se conservan.', 'Liberar espacio')) return;
            try { const r = await api('POST', '/api/limpieza', {}); aviso(`Se liberaron ${r.liberadosMB} MB.`, 'ok'); } catch (err) { avisarError(err); }
          }, '', { icono: 'i-basura' })),
        seccion('i-info', 'La herramienta', `Versión ${app.version}.`, el('div', { class: 'acciones-fila' }, btn('Ver la guía de inicio', () => bienvenida(), '', { icono: 'i-chispa' }), btn('Cerrar la herramienta', cerrarHerramienta, 'peligro', { icono: 'i-apagar' })))));
    await pintarDefaults();
  }
  async function cerrarHerramienta() {
    if (!await confirmar('¿Cerrar la herramienta?', 'Para volver a abrirla, usá el acceso directo "Reportes de cierre". Igual se apaga sola después de tres horas sin uso.', 'Cerrar', 'aviso')) return;
    try {
      await api('POST', '/api/cerrar', {});
      if (estado.fuente) estado.fuente.close();
      limpiar($('#vista')).appendChild(el('div', { class: 'vacio entrar' }, el('div', { class: 'ilustracion' }, icono('i-apagar')), el('h2', null, 'La herramienta se cerró'), el('p', null, 'Podés cerrar esta pestaña. Para volver, usá el acceso directo.')));
    } catch (err) { avisarError(err); }
  }

  // ---------------------------------------------------------------- arranque
  // El tema guardado en la configuración manda (claro por defecto); el del navegador sólo evita un parpadeo al abrir.
  try { aplicarTema(localStorage.getItem('reportes-tema') || 'claro'); } catch (err) { aplicarTema('claro'); }
  $('#btn-tema').addEventListener('click', async () => {
    const nuevo = document.documentElement.dataset.tema === 'oscuro' ? 'claro' : 'oscuro';
    aplicarTema(nuevo);
    try { await api('PATCH', '/api/configuracion', { tema: nuevo }); } catch (err) { /* queda en el navegador */ }
  });
  $('#btn-ayuda').addEventListener('click', ev => {
    ev.stopPropagation();
    abrirMenu($('#btn-ayuda'), [
      { titulo: 'Ayuda' },
      { icono: 'i-chispa', texto: 'Guía de inicio', detalle: 'Un recorrido corto por la herramienta', onclick: () => bienvenida() },
      { icono: 'i-cierre', texto: 'Cómo es un cierre', onclick: () => abrirAyuda('primeros') },
      { icono: 'i-check-circulo', texto: 'Revisar los resultados', onclick: () => abrirAyuda('revision') },
      { icono: 'i-balanza', texto: 'Qué significa cada resultado', detalle: 'De la conciliación general', onclick: () => abrirAyuda('conciliacion') },
      { icono: 'i-mensaje', texto: 'Preguntas frecuentes', onclick: () => abrirAyuda('faq') },
      { icono: 'i-alerta', texto: 'Si algo sale mal', onclick: () => abrirAyuda('problemas') },
      'sep',
      { icono: 'i-info', texto: 'Acerca de la herramienta', onclick: acercaDe },
    ]);
  });
  $('#btn-menu').addEventListener('click', ev => {
    ev.stopPropagation();
    abrirMenu($('#btn-menu'), [
      { icono: 'i-ajustes', texto: 'Configuración', onclick: () => { location.hash = '#/configuracion'; } },
      { icono: 'i-historial', texto: 'Historial', onclick: () => { location.hash = '#/historial'; } },
      'sep',
      { icono: 'i-apagar', texto: 'Cerrar la herramienta', peligro: true, onclick: cerrarHerramienta },
    ]);
  });
  window.addEventListener('hashchange', enrutar);
  (async () => {
    try {
      estado.conf = await api('GET', '/api/configuracion');
      aplicarTema(estado.conf.tema || 'claro');
    } catch (err) { /* sigue con lo local */ }
    conectarEventos();
    actualizarIndicador();
    enrutar();
  })();
})();

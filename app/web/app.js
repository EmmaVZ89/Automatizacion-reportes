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
    const alTocar = onclick ? ev => {
      if (b.classList.contains('cargando')) return;
      const r = onclick(ev);
      if (r && typeof r.then === 'function') {
        const antes = b.disabled;
        b.classList.add('cargando');
        b.setAttribute('aria-busy', 'true');
        b.disabled = true;
        r.finally(() => { b.classList.remove('cargando'); b.removeAttribute('aria-busy'); b.disabled = antes; });
      }
    } : null;
    const b = el('button', { type: 'button', class: 'btn ' + clase, onclick: alTocar, title: opciones.title, disabled: opciones.disabled, 'aria-label': opciones.aria });
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
  // Cambia un texto sólo si es distinto (no toca el nodo si no hace falta).
  const ponerTexto = (nodo, texto) => { if (nodo && nodo.textContent !== texto) nodo.textContent = texto; };
  function progresoGlobal(delta) {
    estado.cargas = Math.max(0, estado.cargas + delta);
    $('#progreso-global').classList.toggle('activo', estado.cargas > 0);
  }
  async function api(metodo, ruta, cuerpo, opciones = {}) {
    const init = { method: metodo, credentials: 'same-origin', headers: {} };
    if (opciones.crudo) { init.body = cuerpo; Object.assign(init.headers, opciones.cabeceras || {}); }
    else if (cuerpo !== undefined) { init.headers['Content-Type'] = 'application/json'; init.body = JSON.stringify(cuerpo); }
    let mostrada = false;
    const lento = opciones.silencioso ? 0 : setTimeout(() => { mostrada = true; progresoGlobal(1); }, 250);
    let r;
    try {
      r = await fetch(ruta, init);
    } catch (e) {
      revisarConexion();
      throw new Error('No se pudo hablar con la herramienta. Si la cerraste, volvé a abrirla desde su acceso directo.');
    } finally {
      clearTimeout(lento);
      if (mostrada) progresoGlobal(-1);
    }
    const tipo = r.headers.get('Content-Type') || '';
    const datos = tipo.includes('json') ? await r.json() : await r.text();
    if (r.status === 403) revisarConexion();  // la herramienta se volvió a abrir: esta pestaña quedó con la sesión vieja
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
    const quitar = () => {
      if (!caja.isConnected || caja.classList.contains('saliendo')) return;
      caja.style.setProperty('--alto-aviso', caja.offsetHeight + 'px');
      caja.classList.add('saliendo');
      setTimeout(() => caja.remove(), 330);
    };
    $('#avisos').appendChild(caja);
    setTimeout(quitar, ms);
    return { cerrar: quitar };
  }
  const avisarError = e => aviso(e.message || String(e), 'error', 9000);

  // ---------------------------------------------------------------- diálogos
  const ICONO_TONO = { pregunta: 'i-ayuda', peligro: 'i-alerta', ok: 'i-check', aviso: 'i-alerta', info: 'i-info' };
  function dialogo({ titulo, texto, boton = 'Aceptar', cancelar = 'Cancelar', tono = 'pregunta', campo = null }) {
    return new Promise(resolve => {
      const d = $('#dialogo');
      limpiar(d);
      d.className = 'dialogo tono-' + tono;
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
      ...(pie.length ? [el('div', { class: 'modal-pie' }, pie)] : []));
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

  // ---------------------------------------------------------------- tareas
  // Visor de tareas, como Trabajos en PedidosIA: todo lo que tarda queda listado con su avance y su resultado, y se
  // vuelve a ver desde el botón de la barra. Entran las acciones de la pantalla (descargas, subidas, preparar el Excel
  // de origen) y los reportes que corren. Si se pide de nuevo algo que ya está en curso, se avisa en vez de repetirlo.
  // Lo que pide el usuario muestra además una tarjeta abajo a la derecha que, al terminar, vuela hasta el botón.
  const tareas = (() => {
    const lista = new Map();
    let abierto = false;
    let reloj = null;
    let sinVer = 0;
    let tarjeta = null;
    const activa = t => t.estado === 'curso' || t.estado === 'espera';
    const ICONO_ESTADO = { ok: 'i-check', error: 'i-x', espera: 'i-mano', cancelada: 'i-detener' };
    const duracion = t => {
      const s = Math.max(0, Math.round(((t.fin || Date.now()) - t.inicio) / 1000));
      return s < 60 ? `${s} s` : s < 3600 ? `${Math.floor(s / 60)} min ${String(s % 60).padStart(2, '0')} s` : `${Math.floor(s / 3600)} h ${Math.floor(s % 3600 / 60)} min`;
    };
    const iconoDe = t => el('span', { class: 'tarea-icono' }, t.estado === 'curso' ? el('span', { class: 'girador' }) : icono(ICONO_ESTADO[t.estado] || 'i-info'));
    const filas = new Map();  // clave -> { nodo, estado }: las filas del panel se reusan
    const barraDe = t => el('div', { class: 'tarea-barra' + (t.progreso == null ? ' indeterminada' : '') }, el('div', { style: t.progreso == null ? '' : `width:${Math.max(3, Math.round(t.progreso * 100))}%` }));
    function latir(tipo) {
      const b = $('#btn-tareas');
      if (!b) return;
      b.classList.remove('late', 'late-ok', 'late-error');
      void b.offsetWidth;
      b.classList.add('late', tipo === 'ok' ? 'late-ok' : tipo === 'error' ? 'late-error' : 'late');
    }
    function pintarBoton() {
      const b = $('#btn-tareas');
      if (!b) return;
      const activas = [...lista.values()].filter(activa);
      const espera = activas.some(t => t.estado === 'espera');
      b.classList.toggle('corriendo', activas.some(t => t.estado === 'curso'));
      b.classList.toggle('esperando', espera);
      const una = activas.length === 1 && activas[0].progreso != null ? activas[0].progreso : null;
      b.classList.toggle('con-pct', una != null);
      if (una != null) b.style.setProperty('--pct', Math.round(una * 100) + '%');
      const n = $('#tareas-n');
      n.textContent = activas.length ? String(activas.length) : '';
      n.className = 'tareas-n' + (activas.length ? (espera ? ' espera' : '') : sinVer ? ' punto' : ' oculto');
      const texto = activas.length ? `${activas.length === 1 ? 'una' : activas.length} en curso${espera ? '; una espera tu acción' : ''}` : sinVer ? 'hay resultados sin ver' : 'nada en curso';
      b.title = 'Tareas: ' + texto;
      b.setAttribute('aria-label', 'Tareas: ' + texto);
    }
    // Fila de hasta tres renglones: nombre y tiempo; detalle y acciones; barra de avance (sólo mientras corre).
    function crearFila(t) {
      const nodo = el('div', { class: 'tarea-fila ' + t.estado }, iconoDe(t),
        el('div', { class: 'tarea-textos' },
          el('div', { class: 'tarea-linea' }, el('b', { class: 'tarea-nombre' }), el('span', { class: 'tarea-tiempo' })),
          el('div', { class: 'tarea-linea' }, el('span', { class: 'tarea-detalle' }),
            el('span', { class: 'tarea-acciones' },
              t.enlace ? el('a', { class: 'tarea-ver', href: t.enlace, onclick: () => abrir(false) }, t.estado === 'espera' ? 'Ir a continuar' : 'Ver') : null,
              t.cancelar && activa(t) ? el('button', { type: 'button', class: 'tarea-cancelar', title: 'Cancelar', 'aria-label': 'Cancelar ' + t.titulo, onclick: () => t.cancelar() }, icono('i-detener')) : null)),
          t.estado === 'curso' ? barraDe(t) : null));
      return { nodo, estado: t.estado };
    }
    function actualizarFila(f, t) {
      const nombre = f.nodo.querySelector('.tarea-nombre');
      ponerTexto(nombre, t.titulo);
      nombre.title = t.titulo;
      const tiempo = f.nodo.querySelector('.tarea-tiempo');
      ponerTexto(tiempo, duracion(t));
      tiempo.title = activa(t) ? 'En curso desde hace ' + duracion(t) : 'Tardó ' + duracion(t);
      const texto = (activa(t) ? t.detalle : (t.resultado || t.detalle)) || '';
      const detalle = f.nodo.querySelector('.tarea-detalle');
      ponerTexto(detalle, texto);
      detalle.title = texto;
      const relleno = f.nodo.querySelector('.tarea-barra > div');
      if (relleno) {
        relleno.parentNode.classList.toggle('indeterminada', t.progreso == null);
        if (t.progreso != null) relleno.style.width = Math.max(3, Math.round(t.progreso * 100)) + '%';
      }
    }
    function pintarPanel() {
      const p = $('#panel-tareas');
      if (!p || !abierto) return;
      const todas = [...lista.values()].sort((a, b) => (Number(activa(b)) - Number(activa(a))) || (b.inicio - a.inicio));
      const cuerpo = p.querySelector('.tareas-lista');
      for (const [clave, f] of filas) if (!lista.has(clave)) { f.nodo.remove(); filas.delete(clave); }
      const vacio = cuerpo.querySelector('.tareas-vacio');
      if (!todas.length && !vacio) cuerpo.appendChild(el('div', { class: 'tareas-vacio' }, icono('i-tareas', 'g'), el('p', null, 'No hay tareas. Acá aparece lo que tarda (reportes que corren, Excel que se arman, archivos que se suben), con su avance y su resultado.')));
      if (todas.length && vacio) vacio.remove();
      todas.forEach((t, i) => {
        let f = filas.get(t.clave);
        if (!f || f.estado !== t.estado) {
          const nueva = crearFila(t);
          if (f) f.nodo.replaceWith(nueva.nodo);
          f = nueva;
          filas.set(t.clave, f);
        }
        actualizarFila(f, t);
        if (cuerpo.children[i] !== f.nodo) cuerpo.insertBefore(f.nodo, cuerpo.children[i] || null);
      });
      p.querySelector('.tareas-limpiar').disabled = !todas.some(t => !activa(t));
    }
    function cambio(t) {
      pintarBoton();
      if (abierto) pintarPanel();
      actualizarTarjeta(t);
    }
    function terminada(t, tipo) {
      latir(tipo);
      if (!abierto) sinVer++;
    }
    function abrir(v = !abierto) {
      const p = $('#panel-tareas');
      abierto = v;
      p.classList.toggle('oculto', !v);
      $('#btn-tareas').setAttribute('aria-expanded', String(v));
      clearInterval(reloj);
      if (!v) return;
      cerrarMenu();
      sinVer = 0;
      pintarBoton();
      pintarPanel();
      reloj = setInterval(() => { if ([...lista.values()].some(activa)) pintarPanel(); }, 1000);
    }
    document.addEventListener('mousedown', ev => { if (abierto && !ev.target.closest('#panel-tareas, #btn-tareas, dialog')) abrir(false); });
    document.addEventListener('keydown', ev => { if (abierto && ev.key === 'Escape' && !document.querySelector('dialog[open]')) abrir(false); });

    // ---- tarjeta de la acción en curso (abajo a la derecha, arriba de los avisos)
    function quitarTarjeta(volar) {
      if (!tarjeta) return;
      const { nodo, timer } = tarjeta;
      clearTimeout(timer);
      tarjeta = null;
      const b = $('#btn-tareas');
      if (!volar || !b || !nodo.isConnected) { nodo.remove(); return; }
      const a = nodo.getBoundingClientRect();
      const c = b.getBoundingClientRect();
      const vuelo = nodo.animate([{ transform: 'none', opacity: 1 }, { transform: `translate(${c.left + c.width / 2 - (a.left + a.width / 2)}px, ${c.top + c.height / 2 - (a.top + a.height / 2)}px) scale(.12)`, opacity: .2 }],
        { duration: 520, easing: 'cubic-bezier(.55,0,.7,.2)', fill: 'forwards' });
      vuelo.finished.then(() => { nodo.remove(); latir(); }, () => nodo.remove());
    }
    function mostrarTarjeta(t) {
      quitarTarjeta(false);
      const nodo = el('div', { class: 'tarea-tarjeta', role: 'status', title: 'Tocá para mandarla a Tareas' });
      nodo.addEventListener('click', () => quitarTarjeta(true));
      tarjeta = { nodo, clave: t.clave, timer: null, estado: null };
      $('#avisos').prepend(nodo);
      actualizarTarjeta(t);
    }
    function actualizarTarjeta(t) {
      if (!tarjeta || tarjeta.clave !== t.clave) return;
      const n = tarjeta.nodo;
      if (tarjeta.estado !== t.estado) {
        tarjeta.estado = t.estado;
        n.className = 'tarea-tarjeta ' + t.estado;
        limpiar(n).append(iconoDe(t), el('div', { class: 'tarea-textos' }, el('b', null, t.titulo), el('div', { class: 'tarea-detalle' }), t.estado === 'curso' ? barraDe(t) : ''));
        if (!activa(t)) tarjeta.timer = setTimeout(() => quitarTarjeta(true), t.estado === 'error' ? 9000 : 3200);
      }
      n.querySelector('.tarea-detalle').textContent = activa(t) ? (t.detalle || 'Trabajando…') : (t.resultado || '');
      const relleno = n.querySelector('.tarea-barra > div');
      if (relleno && t.progreso != null) { relleno.parentNode.classList.remove('indeterminada'); relleno.style.width = Math.max(3, Math.round(t.progreso * 100)) + '%'; }
    }

    // ---- tareas de la pantalla
    function iniciar({ clave, titulo, detalle = '', enlace = null, progreso = null, conTarjeta = true }) {
      const t = { clave, titulo, detalle, enlace, progreso, estado: 'curso', inicio: Date.now(), fin: null, resultado: '' };
      lista.set(clave, t);
      latir();
      pintarBoton();
      if (abierto) pintarPanel();
      if (conTarjeta) mostrarTarjeta(t);
      return {
        avance(p, d) { if (lista.get(clave) !== t || !activa(t)) return; if (p !== undefined) t.progreso = p; if (d != null) t.detalle = d; cambio(t); },
        terminar(texto = 'Listo', tipo = 'ok') {
          if (lista.get(clave) !== t || !activa(t)) return;
          t.estado = tipo === 'error' ? 'error' : 'ok';
          t.fin = Date.now();
          t.resultado = texto;
          t.progreso = null;
          cambio(t);
          terminada(t, t.estado);
        },
      };
    }
    const enCurso = clave => { const t = lista.get(clave); return t && activa(t) ? t : null; };
    // Corre `fn` como tarea. Si ya hay una con la misma clave en curso, avisa y no la repite (devuelve undefined).
    async function correr(opciones, fn, textoRepetida) {
      const ya = enCurso(opciones.clave);
      if (ya) {
        aviso(textoRepetida || `Ya está en curso: ${ya.titulo}. Te aviso cuando termine; lo ves en Tareas.`, 'info', 4500);
        latir();
        return undefined;
      }
      const t = iniciar(opciones);
      try {
        const r = await fn(t);
        t.terminar(typeof r === 'string' ? r : 'Listo');
        return r;
      } catch (err) {
        t.terminar(err.message || String(err), 'error');
        throw err;
      }
    }

    // ---- reportes que corren y copias del Excel de origen (llegan por los eventos)
    const ESTADO_TRABAJO = { corriendo: 'curso', esperando: 'espera', ok: 'ok', error: 'error', cancelado: 'cancelada', interrumpido: 'error' };
    function desdeTrabajo(tr, inicial = false) {
      const clave = 'trabajo:' + tr.id;
      const previa = lista.get(clave);
      const nuevo = ESTADO_TRABAJO[tr.estado] || 'curso';
      const t = previa || { clave, inicio: (tr.inicio || Date.now() / 1000) * 1000 };
      const antes = previa ? previa.estado : null;
      Object.assign(t, {
        titulo: tr.titulo || 'Reporte', estado: nuevo,
        progreso: nuevo === 'curso' && typeof tr.progreso === 'number' ? tr.progreso : null,
        detalle: nuevo === 'espera' ? 'Espera tu acción: entrá y seguí las indicaciones.' : (tr.paso || ''),
        resultado: nuevo === 'ok' ? 'Terminó bien: ya podés revisar los resultados.' : nuevo === 'cancelada' ? 'Se canceló.' : nuevo === 'error' ? (tr.error || 'Terminó con un error.') : '',
        fin: tr.fin ? tr.fin * 1000 : null, interrumpida: false,
        enlace: `#/ejecucion/${encodeURIComponent(tr.ejecucionId)}/${nuevo === 'ok' ? 4 : 3}`,
        cancelar: async () => {
          if (!await confirmar('¿Cancelar el reporte?', 'Se detiene la corrida. Podés volver a correrlo cuando quieras.', 'Cancelar el reporte', 'peligro')) return;
          try { await api('POST', `/api/trabajos/${tr.id}/cancelar`, {}); } catch (err) { avisarError(err); }
        },
      });
      lista.set(clave, t);
      if (!inicial && !previa) latir();
      if (!inicial && antes && antes !== nuevo && !activa(t)) terminada(t, nuevo === 'ok' ? 'ok' : 'error');
      pintarBoton();
      if (abierto) pintarPanel();
    }
    function desdeOrigen(o) {
      const clave = 'origen:' + o.ejecucionId;
      let t = lista.get(clave);
      if (t && t.interrumpida) Object.assign(t, { interrumpida: false, estado: 'curso', fin: null, resultado: '' });
      if (!t || (!activa(t) && !o.listo && !o.error)) {
        t = { clave, titulo: 'Preparando el Excel de origen', detalle: 'Copia de consulta de los Excel de entrada; se hace una sola vez.', inicio: Date.now(), estado: 'curso', progreso: 0, fin: null, resultado: '' };
        lista.set(clave, t);
        latir();
      }
      if (o.error) { if (activa(t)) { t.estado = 'error'; t.resultado = o.error; t.fin = Date.now(); t.progreso = null; terminada(t, 'error'); } }
      else if (o.listo) { if (activa(t)) { t.estado = 'ok'; t.resultado = 'Listo: el Excel de origen de cada fila sale al instante.'; t.fin = Date.now(); t.progreso = null; terminada(t, 'ok'); } }
      else { t.estado = 'curso'; t.progreso = typeof o.progreso === 'number' ? o.progreso : null; }
      cambio(t);
    }
    // Se perdió la conexión: los reportes y las copias en curso no van a avisar que terminaron.
    function interrumpir(texto) {
      for (const t of lista.values()) {
        if (!activa(t) || !/^(origen|trabajo):/.test(t.clave)) continue;
        Object.assign(t, { estado: 'error', interrumpida: true, resultado: texto, fin: Date.now(), progreso: null });
        cambio(t);
      }
    }
    const origenesPendientes = () => [...lista.values()].filter(t => t.clave.startsWith('origen:') && (activa(t) || t.interrumpida)).map(t => t.clave.slice(7));
    function sacarTerminadas() {
      for (const [k, t] of lista) if (!activa(t)) lista.delete(k);
      sinVer = 0;
      pintarBoton();
      pintarPanel();
    }
    return { iniciar, correr, enCurso, desdeTrabajo, desdeOrigen, interrumpir, origenesPendientes, abrir, sacarTerminadas, pintarBoton };
  })();
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
      ['ul', ['Arrastrá los archivos a la zona punteada, o usá "Elegir archivos".', 'Si el archivo ya está en una carpeta de la PC, "Tomar de una carpeta" lo copia sin tocar el original.', 'Si el sistema cortó la descarga en dos o más archivos (pasa cerca de las 454.000 filas), agregá todos: se leen seguidos como uno solo.', 'Un archivo que se usa en varios reportes del mes (como el histórico de SGA) se sube una sola vez y queda disponible para los demás.', 'El tacho al lado de cada archivo lo quita del cierre (el original de tu PC no se toca). Los que la herramienta no reconoce, como un Excel exportado que se subió por error, aparecen aparte en "Archivos del cierre que no reconocí" y también se pueden quitar.']],
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
      ['ul', ['A la izquierda, las tablas de cada Excel del reporte van bajo su título (por ejemplo, Control Netos Impuestos con MORA, Mes en curso e Histórico). Tocá el título para abrirlas o cerrarlas.', 'Hacé clic en una fila (o en varias) y usá "Revisada" u "Omitir". "Pendiente" deshace la marca.', 'Escribí una observación y guardala para las filas marcadas, o hacé doble clic en la columna de observaciones de una fila.', '"Para revisar" muestra sólo las filas que hay que mirar (en la conciliación, las que no dan COINCIDE). Las demás están en "Todas" con la marca "No requiere" y no cuentan como pendientes.', 'Buscá, filtrá por estado y ordená tocando el título de cada columna.', 'Lo que marques se guarda solo y pasa a la próxima versión del mismo mes. Con "Traer la revisión del cierre anterior" recuperás lo que ya habías omitido el mes pasado.']],
      ['p', 'Tu vista de la tabla:'],
      ['ul', ['El embudo de cada título filtra como en Excel. En las columnas de texto tildás los valores: la lista muestra lo que queda con los otros filtros y se puede buscar escribiendo. En los importes elegís una condición: distinto de cero, igual, mayor, menor o entre dos valores. Los filtros activos se ven arriba de la tabla y se quitan con la cruz.', '"Columnas" elige qué columnas ver y en qué orden. También podés arrastrar el título de una columna para moverla. La vista queda guardada para ese reporte.', 'El botón "Exportar" de la barra de la tabla baja un Excel con todas las filas del filtro elegido (no sólo la página que estás viendo), con tus columnas en tu orden.', 'En la conciliación, el botón verde de cada fila baja un Excel con las filas de SGA y de ERP que la forman, con las columnas del archivo original. En Control Netos Impuestos baja la fila del histórico de SGA con las celdas a completar o corregir en anaranjado, como en pantalla. La primera vez tarda alrededor de un minuto en prepararse.']],
    ] },
    exportar: { titulo: 'Paso 5: Exportar', icono: 'i-bajar', partes: [
      ['p', 'Armás el Excel que necesitás en lugar de bajar todo el reporte:'],
      ['ul', ['Qué filas: las que hay que revisar, todas, o sólo algunos valores del resultado (por ejemplo, DIFERENCIA).', 'Qué estado de revisión: pendientes, revisadas u omitidas, y si querés sólo las que tienen observación.', 'Qué columnas: las de tu vista de Resultados, en tu orden, o todas. Podés sumar la hoja Resumen al principio.', 'Antes de bajarlo te dice cuántas filas va a tener.']],
      ['ul', ['"Libros completos del reporte" baja el libro entero con todas sus solapas y tu revisión, por si lo necesitás así.', 'Marcá la versión como "resultado final del cierre" cuando ya esté revisada: así queda registrada en el historial.']],
    ] },
  };
  const AYUDA_GENERAL = [
    { clave: 'primeros', titulo: 'Cómo es un cierre', icono: 'i-cierre', partes: [
      ['ol', ['Creá el cierre del mes (botón "Nuevo cierre") con su fecha de corte.', 'Entrá a cada reporte del cierre y seguí sus cinco pasos: Archivos, Opciones, Ejecución, Resultados y Exportar.', 'Revisá los resultados: marcá filas como revisadas u omitidas y anotá observaciones.', 'Cuando un reporte quede listo, marcalo como resultado final. Con todos los reportes finales (la Conciliación general, de los dos fondos), el cierre está completo.']],
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
      ['p', 'Fecha SGA y Fecha ERP: la fecha del comprobante en cada sistema. En SGA es la de la factura, o la del comprobante de imputación cuando la fila es de un recibo, subrecibo o pendiente; en ERP, la Fecha de la transacción. Si una está vacía, ese sistema no tiene el comprobante o no trae la fecha.'],
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
        ['¿Dónde veo lo que está tardando?', 'En el botón de Tareas, arriba a la derecha, al lado de Ayuda. Muestra los reportes que corren, los Excel que se arman y los archivos que se suben, con su avance y su resultado. Si pedís de nuevo algo que ya está en curso, la herramienta te avisa en lugar de repetirlo.'],
        ['Apareció una franja que dice que la herramienta se actualizó', 'Se instaló una versión nueva con la herramienta abierta. Tocá "Reiniciar la herramienta" en la franja: se cierra y se vuelve a abrir sola en unos segundos.'],
        ['¿Cómo reinicio la herramienta?', 'Desde el menú de los tres puntos, "Reiniciar la herramienta". Sirve si algo quedó trabado o después de instalar una versión nueva. Lo que tenés guardado no se pierde; si hay un reporte corriendo, te pide que esperes o lo canceles.'],
        ['¿Cómo cierro la herramienta?', 'Desde el menú de los tres puntos, "Cerrar la herramienta". Si la dejás abierta en el navegador no se apaga; si cerrás la pestaña, se apaga sola tres horas después.'],
        ['¿Dónde está el acceso directo?', 'La herramienta lo crea sola la primera vez que se abre, en el Escritorio, con el nombre "Reportes de cierre". Si lo borraste, en Configuración está "Crear el acceso directo en el Escritorio".']]],
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
      { titulo: 'Un cierre por mes', texto: 'Creás el cierre del mes con su fecha de corte. Adentro están sus reportes: la Conciliación general (una por fondo de riesgo: Fondo General y FERF Prov. Santa Fe), Controles SGA, Control de Mora y Control de cheques.' },
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
    marcarNav({ inicio: 'inicio', cierres: 'cierres', cierre: 'cierres', ejecucion: 'cierres', facturas: 'facturas', historial: 'historial', configuracion: 'inicio' }[vista]);
    estado.vista = { nombre: vista, partes };
    detenerSondeo();
    soltarCabecera();
    cerrarPopoverFiltro();
    cerrarMenu();
    const r = { inicio: () => vistaInicio(), cierres: () => vistaInicio(true), cierre: () => vistaCierre(partes[1]), ejecucion: () => vistaEjecucion(partes[1], partes[2]), facturas: vistaFacturas, historial: vistaHistorial, configuracion: async () => { history.replaceState(null, '', '#/inicio'); await vistaInicio(); await abrirConfiguracion(); } }[vista];
    return (r || vistaInicio)().catch(avisarError);
  }
  // Vacía #vista para la pantalla nueva y le da su ancho recién ahora, junto con el contenido nuevo (si se hacía al
  // cambiar de dirección, la pantalla anterior se estiraba o se achicaba un instante mientras llegaban los datos).
  function pantallaNueva() {
    const v = $('#vista');
    v.classList.toggle('ancha', !!estado.vista && estado.vista.nombre === 'ejecucion');
    return limpiar(v);
  }
  function marcarNav(nav) {
    for (const a of document.querySelectorAll('[data-nav]')) a.classList.toggle('activa', a.dataset.nav === nav);
  }
  function detenerSondeo() { if (estado.sondeo) { clearInterval(estado.sondeo); estado.sondeo = null; } }
  function conectarEventos() {
    if (estado.fuente) estado.fuente.close();
    const f = new EventSource('/api/eventos');
    estado.fuente = f;
    f.addEventListener('trabajo', ev => { const t = JSON.parse(ev.data); tareas.desdeTrabajo(t); if (estado.w && estado.w.e && estado.w.e.trabajoId === t.id) pintarTrabajo(t); });
    f.addEventListener('origen', ev => {
      const o = JSON.parse(ev.data);
      tareas.desdeOrigen(o);
      const pendiente = origenPendiente.get(o.ejecucionId);
      if (o.listo && pendiente) { origenPendiente.delete(o.ejecucionId); pendiente().catch(avisarError); }
      if (o.error) origenPendiente.delete(o.ejecucionId);
    });
    f.addEventListener('ejecucion', ev => {
      const e = JSON.parse(ev.data);
      if (estado.w && estado.w.e && estado.w.e.id === e.id && !e.borrado) {
        const antes = estado.w.e.estado;
        if (antes !== e.estado) {
          if (e.estado === 'ok' && (antes === 'corriendo' || antes === 'esperando')) aviso(`${estado.w.reporte.nombre}: terminó bien. Ya podés revisar los resultados.`, 'ok');
          enSilencio(() => vistaEjecucion(e.id, e.estado === 'ok' ? '4' : undefined, true));
        }
      } else if (estado.vista && ['inicio', 'cierres', 'cierre', 'historial', 'facturas'].includes(estado.vista.nombre)) enSilencio(enrutar);
    });
    f.addEventListener('cierre', () => { if (estado.vista && ['inicio', 'cierres'].includes(estado.vista.nombre)) enSilencio(enrutar); });
    f.onopen = () => { if (estado.eventosAbiertos++ > 0 || conexion.perdida) reconectada(); };
    f.onerror = () => { revisarConexion(); setTimeout(() => { if (estado.fuente === f) conectarEventos(); }, 5000); };
  }
  // Redibujo que no pidió el usuario (llegó un evento): sin las animaciones de entrada, para que no parpadee.
  async function enSilencio(fn) {
    const v = $('#vista');
    v.classList.add('quieta');
    try { await fn(); } catch (err) { avisarError(err); }
    finally { setTimeout(() => v.classList.remove('quieta'), 120); }
  }
  // La herramienta se actualizó con la pantalla abierta: el código nuevo recién corre al cerrarla y abrirla.
  // Conexión con la herramienta. Si se cierra (o se apaga la PC), la pantalla lo dice en lugar de quedar esperando y
  // los reportes y copias en curso pasan a interrumpidos. Si vuelve (la PC se despertó), se pone al día.
  const conexion = { perdida: false, revisando: false };
  estado.eventosAbiertos = 0;
  async function revisarConexion() {
    if (conexion.revisando || estado.saliendo) return;
    conexion.revisando = true;
    try {
      let status = 0;
      try { status = (await fetch('/api/estado', { credentials: 'same-origin', cache: 'no-store' })).status; } catch (e) { status = 0; }
      if (status === 200) { if (conexion.perdida) await reconectada(); return; }
      if (estado.saliendo) return;
      $('#texto-conexion').textContent = status === 403
        ? 'La herramienta se volvió a abrir en otra pestaña: seguí en esa, o cerrá ésta y abrila con el acceso directo "Reportes de cierre".'
        : 'Se perdió la conexión con la herramienta: se cerró o se apagó la PC. Abrila de nuevo con el acceso directo "Reportes de cierre"; lo que tenías guardado sigue ahí.';
      if (conexion.perdida) return;
      conexion.perdida = true;
      $('#banda-conexion').classList.remove('oculto');
      tareas.interrumpir('Se interrumpió: se perdió la conexión con la herramienta.');
    } finally { conexion.revisando = false; }
  }
  async function reconectada() {
    conexion.perdida = false;
    $('#banda-conexion').classList.add('oculto');
    const st = await revisarVersion();
    if (!st) return;
    // Lo que se pudo perder mientras no había conexión: copias que terminaron, reportes que cambiaron de estado.
    const enServidor = new Set((st.origenes || []).map(o => o.ejecucionId));
    for (const o of st.origenes || []) tareas.desdeOrigen(o);
    for (const id of tareas.origenesPendientes().filter(x => !enServidor.has(x))) {
      try {
        const o = await api('GET', `/api/ejecuciones/${encodeURIComponent(id)}/origen/estado`, undefined, { silencioso: true });
        tareas.desdeOrigen({ ejecucionId: id, listo: !!o.listo, error: o.listo ? null : (o.error || 'Se interrumpió. Entrá a Resultados de esa versión para retomarla.') });
      } catch (err) { /* queda como está */ }
    }
    try {
      const desde = Date.now() / 1000 - 12 * 3600;
      for (const tr of await api('GET', '/api/trabajos', undefined, { silencioso: true })) if ((tr.inicio || 0) >= desde) tareas.desdeTrabajo(tr);
    } catch (err) { /* queda como está */ }
  }
  async function revisarVersion() {
    try {
      const st = await api('GET', '/api/estado', undefined, { silencioso: true });
      $('#banda-version').classList.toggle('oculto', !st.reiniciar);
      return st;
    } catch (err) { return null; }
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
  // La variante de una ejecución (el fondo de riesgo, en la conciliación): {valor, titulo, corto}, o null.
  function varianteDe(reporte, e) {
    const v = reporte && reporte.variantes;
    if (!v) return null;
    const valor = (e && (e.variante || (e.parametros || {})[v.parametro])) || v.opciones[0].valor;
    return v.opciones.find(o => o.valor === valor) || v.opciones[0];
  }
  const chipVariante = (variante, clase = '') => variante ? el('span', { class: ('chip fondo ' + clase).trim(), title: 'Fondo de riesgo de esta conciliación' }, icono('i-caja'), variante.titulo) : null;
  // Lo que tiene que quedar listo en un cierre: un ítem por reporte, o uno por variante (cada fondo de la conciliación
  // es obligatorio y tiene sus versiones y su resultado final).
  function itemsCierre(c) {
    const items = [];
    for (const r of reportesCierre()) {
      const info = c.reportes[r.codigo] || null;
      if (r.variantes) for (const o of r.variantes.opciones) items.push({ r, variante: o, info: (info && info.variantes && info.variantes[o.valor]) || null });
      else items.push({ r, variante: null, info });
    }
    return items;
  }
  function resumenCierre(c) {
    const lista = itemsCierre(c);
    let finales = 0, terminados = 0, curso = 0, pendientesRev = 0;
    for (const { info } of lista) {
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
  async function vistaInicio(soloCierres = false) {
    const sello = nuevoSello();
    estado.w = null;
    const [cierres, app] = await Promise.all([api('GET', '/api/cierres'), api('GET', '/api/estado')]);
    if (!vigente(sello)) return;
    estado.app = app;
    const main = pantallaNueva();
    const actual = periodoDe(hoy());
    const enCurso = cierres.find(c => !c.cerrado && !c.importado) || null;
    const contenedor = el('div', { class: 'escalonado' });
    main.appendChild(contenedor);
    const importar = el('input', { type: 'file', accept: '.zip', class: 'visual-oculto', 'aria-label': 'Importar un cierre exportado' });
    importar.addEventListener('change', async () => {
      const f = importar.files[0];
      if (!f) return;
      try { const c = await tareas.correr({ clave: 'importar:' + f.name, titulo: `Importando ${f.name}` }, async () => api('POST', '/api/cierres/importar', f, { crudo: true, cabeceras: { 'Content-Type': 'application/zip' } })); if (!c) return; aviso(`Se importó el cierre de ${periodoLargo(c.periodo)} (sólo para ver).`, 'ok'); enrutar(); } catch (e) { avisarError(e); }
      importar.value = '';
    });
    if (soloCierres) {
      contenedor.appendChild(el('div', { class: 'encabezado entrar' }, el('div', null, el('h1', null, 'Cierres'),
        el('div', { class: 'sub' }, 'Cada cierre agrupa los reportes de un mes. Entrá a uno para correr sus reportes o ver sus resultados.'))));
    } else if (!enCurso) {
      contenedor.appendChild(el('section', { class: 'hero' }, el('div', { class: 'hero-cuadricula' }), el('div', { class: 'hero-brillo' }),
        el('div', { class: 'hero-texto' },
          el('span', { class: 'hero-etiqueta' }, icono('i-chispa'), cierres.length ? 'Todo al día' : 'Para empezar'),
          el('h1', null, cierres.length ? `Empezá el cierre de ${periodoLargo(actual).toLowerCase()}` : 'Empezá tu primer cierre'),
          el('p', { class: 'bajada' }, 'Un cierre agrupa los reportes del mes. Lo creás con su fecha de corte y después corrés cada reporte paso a paso.'),
          el('div', { class: 'acciones-fila' },
            btn(`Crear el cierre de ${periodoLargo(actual).toLowerCase()}`, () => nuevoCierre(cierres.some(c => c.periodo === actual) ? null : actual).catch(avisarError), 'primario grande llama', { icono: 'i-mas' }),
            btn('Ver cómo funciona', () => bienvenida(), 'fantasma', { icono: 'i-libro' }))),
        el('div', { class: 'hero-anillo' }, el('div', { class: 'tile grande', style: 'width:96px;height:96px;border-radius:26px;background:var(--panel);color:var(--accent);box-shadow:var(--sombra-media)' }, icono('i-cierre', 'xg')))));
    } else {
      const res = resumenCierre(enCurso);
      const listos = res.finales + res.terminados;
      const bajada = res.sinCorrer === res.total ? 'Todavía no corriste ningún reporte de este cierre. Empezá por el que tengas los archivos listos.'
        : res.finales === res.total ? 'Todos los reportes tienen su resultado final. El cierre está completo.'
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
        el('div', { class: 'mini-reportes' }, itemsCierre(c).map(({ r, variante, info }) =>
          el('span', { class: 'mini-reporte ' + claseEstado(info), title: textoEstadoReporte(info, r, variante) }, tileReporte(r), variante ? el('b', { class: 'mini-variante' }, variante.corto) : null,
            info && info.final ? 'Final' : info && info.ultima ? (ESTADO_TEXTO[info.ultima.estado] || '') : 'Sin correr'))),
        el('span', { class: 'chip ' + (res.finales === res.total ? 'ok' : 'borde') }, `${res.finales + res.terminados}/${res.total}`)));
    }
    contenedor.appendChild(lista);
    if (!soloCierres && estado.conf && !estado.conf.bienvenida) bienvenida(empezar => { if (empezar && !cierres.length) nuevoCierre(actual).catch(avisarError); });
  }
  function textoEstadoReporte(info, r, variante = null) {
    const nombre = r.nombre + (variante ? ` (${variante.titulo})` : '');
    if (!info || !info.ultima) return `${nombre}: sin correr`;
    const u = info.final || info.ultima;
    return `${nombre}: ${ESTADO_TEXTO[u.estado] || u.estado}, versión ${u.version}` + (u.estado === 'ok' ? (u.revision.pendientes === 1 ? ', una fila pendiente' : `, ${n(u.revision.pendientes)} filas pendientes`) : '') + (info.final ? ', resultado final' : '');
  }

  // ---------------------------------------------------------------- vista: cierre
  async function vistaCierre(id) {
    const sello = nuevoSello();
    estado.w = null;
    const [c, app] = await Promise.all([api('GET', '/api/cierres/' + encodeURIComponent(id)), api('GET', '/api/estado')]);
    if (!vigente(sello)) return;
    estado.app = app;
    if (c.herramienta) { location.hash = '#/facturas'; return; }
    const main = pantallaNueva();
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
      { icono: 'i-caja', texto: 'Exportar el cierre', detalle: 'Un archivo para compartirlo con otra persona', onclick: () => exportarCierre(c) },
      { icono: c.cerrado ? 'i-deshacer' : 'i-bandera', texto: c.cerrado ? 'Reabrir el cierre' : 'Marcar el cierre como completo', onclick: async () => { try { await api('PATCH', '/api/cierres/' + encodeURIComponent(c.id), { cerrado: !c.cerrado }); if (!c.cerrado) { aviso(`Cierre de ${periodoLargo(c.periodo)} completo.`, 'ok'); } enrutar(); } catch (e) { avisarError(e); } } },
      'sep',
      { icono: 'i-basura', texto: 'Borrar el cierre', peligro: true, onclick: async () => {
        const tieneFinal = Object.values(c.reportes).some(r => r.final);
        if (!await confirmar('¿Borrar este cierre?', (tieneFinal ? 'Tiene resultados finales. ' : '') + 'Se pierden todas sus corridas, archivos y revisiones. No se puede deshacer.', 'Borrar el cierre', 'peligro')) return;
        try { await api('DELETE', `/api/cierres/${encodeURIComponent(c.id)}?forzar=1`); aviso('Cierre borrado.', 'ok'); location.hash = '#/cierres'; } catch (e) { avisarError(e); }
      } },
    ];
    const listos = res.finales + res.terminados;
    main.appendChild(el('div', { class: 'migas' }, el('a', { href: '#/cierres' }, 'Cierres'), icono('i-der'), el('span', null, periodoLargo(c.periodo))));
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
    for (const { r, variante } of itemsCierre(c)) grilla.appendChild(tarjetaReporte(c, r, variante));
    main.appendChild(grilla);
  }
  function tarjetaReporte(c, r, variante = null) {
    const vacio = { versiones: 0, ultima: null, final: null };
    const info = (variante ? ((c.reportes[r.codigo] || {}).variantes || {})[variante.valor] : c.reportes[r.codigo]) || vacio;
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
        const e = await api('POST', '/api/ejecuciones', { cierre: c.id, reporte: r.codigo, variante: variante ? variante.valor : undefined });
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
    tarjeta.append(el('div', { class: 'cabeza' }, tileReporte(r), el('div', null, el('h3', null, r.nombre), variante ? chipVariante(variante, 'en-tarjeta') : null,
      el('div', { class: 'desc' }, variante ? `Conciliación de ${variante.titulo}: el histórico de SGA es el mismo; el ERP, el de este fondo.` : r.descripcion))), estadoFila);
    if (u && u.estado === 'ok') {
      const rev = u.revision;
      tarjeta.append(barraRevision(rev), el('div', { class: 'leyenda-revision' }, el('span', null, el('b', null, n(rev.pendientes)), ' pendientes'), el('span', null, el('b', null, n(rev.revisadas)), ' revisadas'), el('span', null, el('b', null, n(rev.omitidas)), ' omitidas')));
    }
    tarjeta.appendChild(el('div', { class: 'pie' }, el('div', { class: 'acciones-fila' }, principal, secundarios),
      el('div', { class: 'acciones-fila' }, info.versiones > 1 ? enlace(`${info.versiones} versiones`, '#/historial/' + encodeURIComponent(c.id) + '/' + r.codigo + (variante ? '/' + encodeURIComponent(variante.valor) : ''), 'btn enlace chico', 'i-historial') : null,
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
    const main = pantallaNueva();
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
  function soltarCabecera() {
    if (estado.alScroll) { window.removeEventListener('scroll', estado.alScroll); estado.alScroll = null; }
    if (estado.observaCabecera) { estado.observaCabecera.disconnect(); estado.observaCabecera = null; }
    document.documentElement.style.removeProperty('--alto-cabecera');
  }
  // El encabezado del reporte (migas, título y pasos) queda fijo arriba; al bajar se achica para dejar lugar a la tabla.
  // Achicado conserva el alto que ocupaba (margen inferior): si la página se acortara, el navegador corregiría el scroll,
  // el encabezado volvería a agrandarse y la pantalla temblaría entre las dos versiones.
  function fijarCabecera(cabecera) {
    soltarCabecera();
    let compacta = false;
    let altoCompleto = 0;
    const conservarAlto = () => { cabecera.style.marginBottom = compacta ? Math.max(16, altoCompleto - cabecera.offsetHeight) + 'px' : ''; };
    estado.alScroll = () => {
      const y = window.scrollY;
      const nueva = compacta ? y > 8 : (y > 60 && document.documentElement.scrollHeight - window.innerHeight > 220);
      if (nueva === compacta) return;
      if (nueva) altoCompleto = cabecera.offsetHeight;
      compacta = nueva;
      cabecera.classList.toggle('compacta', compacta);
      conservarAlto();
    };
    window.addEventListener('scroll', estado.alScroll, { passive: true });
    estado.observaCabecera = new ResizeObserver(() => {
      conservarAlto();  // sigue la transición del achique
      document.documentElement.style.setProperty('--alto-cabecera', cabecera.offsetHeight + 'px');
    });
    estado.observaCabecera.observe(cabecera);
    estado.alScroll();
  }
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
      grilla: previo ? previo.grilla : null,
      valores: previo ? previo.valores : null, trabajo: null };
    estado.w = w;
    const terminal = ['ok', 'error', 'cancelado'].includes(e.estado);
    const enCurso = e.estado === 'corriendo' || e.estado === 'esperando';
    const pasoDefault = e.estado === 'ok' ? 4 : (enCurso || terminal) ? 3 : (Object.keys(e.entradas || {}).length ? 2 : 1);
    let paso = parseInt(pasoPedido || '', 10) || (previo && !refresco ? previo.paso : pasoDefault);
    if (!terminal && !enCurso && paso > 2) paso = pasoDefault;
    if ((paso === 4 || paso === 5) && e.estado !== 'ok') paso = 3;
    w.paso = paso;
    const main = pantallaNueva();
    const esHerramienta = !!cierre.herramienta;
    marcarNav(esHerramienta ? 'facturas' : 'cierres');
    const volver = esHerramienta ? '#/facturas' : '#/cierre/' + encodeURIComponent(cierre.id);
    const cabecera = el('div', { class: 'cabecera-fija' });
    main.appendChild(cabecera);
    cabecera.appendChild(el('div', { class: 'migas' }, esHerramienta ? el('a', { href: '#/facturas' }, 'Facturas') : [el('a', { href: '#/cierres' }, 'Cierres'), icono('i-der'), el('a', { href: volver }, periodoLargo(cierre.periodo))],
      icono('i-der'), el('span', null, `${reporte.nombre}, versión ${e.version}`)));
    cabecera.appendChild(el('div', { class: 'cabecera-reporte' }, tileReporte(reporte, 'grande'),
      el('div', { class: 'titulos' }, el('h1', null, reporte.nombre),
        el('div', { class: 'meta' }, chipEstado(e), el('span', { class: 'chip borde' }, `Versión ${e.version}`), chipVariante(varianteDe(reporte, e)), esHerramienta ? null : el('span', { class: 'chip borde' }, icono('i-calendario'), periodoLargo(cierre.periodo)), e.final ? el('span', { class: 'chip acento' }, icono('i-bandera'), 'Resultado final') : null)),
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
    cabecera.appendChild(pasos);
    fijarCabecera(cabecera);
    const contenido = el('section', { class: 'tarjeta panel-paso' });
    main.appendChild(contenido);
    await ({ 1: pasoArchivos, 2: pasoOpciones, 3: pasoEjecucion, 4: pasoResultados, 5: pasoExportar }[paso])(contenido, w);
  }
  function intro(iconoNombre, texto) { return el('div', { class: 'intro' }, icono(iconoNombre), el('p', null, texto)); }
  // Crea y corre ya una versión nueva con los mismos archivos y opciones (para una versión de antes de un cambio del
  // reporte). Si no se puede correr (por ejemplo, la limpieza borró un archivo), queda en Opciones para corregirlo.
  function correrNuevaVersion(w) {
    return async () => {
      let nueva = null;
      const datos = { entradas: w.e.entradas || {}, parametros: w.e.parametros || {} };
      try {
        nueva = await api('POST', '/api/ejecuciones', { cierre: w.cierre.id, reporte: w.reporte.codigo, variante: (varianteDe(w.reporte, w.e) || {}).valor });
        await api('PATCH', '/api/ejecuciones/' + encodeURIComponent(nueva.id), datos);
        await api('POST', `/api/ejecuciones/${encodeURIComponent(nueva.id)}/ejecutar`, datos);
        estado.w = null;
        aviso(`Corriendo la versión ${nueva.version}. Cuando termine, lo que revisaste pasa solo.`, 'info');
        location.hash = '#/ejecucion/' + encodeURIComponent(nueva.id) + '/3';
      } catch (err) {
        avisarError(err);
        if (nueva) { estado.w = null; location.hash = '#/ejecucion/' + encodeURIComponent(nueva.id) + '/2'; }
      }
    };
  }
  function nuevaVersion(w) {
    return async () => {
      try {
        const e = await api('POST', '/api/ejecuciones', { cierre: w.cierre.id, reporte: w.reporte.codigo, variante: (varianteDe(w.reporte, w.e) || {}).valor });
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
    const bloques = el('div', { class: 'bloques-entradas' });
    const pie = el('div', { class: 'pie-paso' });
    cont.append(bloques, pie);
    const recargar = async () => { cierre = w.cierre = await api('GET', '/api/cierres/' + encodeURIComponent(cierre.id)); pintar(); };
    // Quita un archivo del cierre: se borra la copia de la herramienta, nunca el original de la PC.
    const quitarArchivo = async a => {
      if (!await confirmar(`¿Quitar ${a.nombre}?`, 'Se borra la copia guardada en la herramienta; el archivo original de tu PC no se toca. Si lo usa alguna versión de este cierre, no se puede quitar.', 'Quitar', 'peligro')) return;
      try {
        await api('DELETE', `/api/cierres/${encodeURIComponent(cierre.id)}/archivos/${encodeURIComponent(a.id)}`);
        for (const s of Object.values(seleccion)) s.delete(a.id);
        recienSubidos.delete(a.id);
        aviso(`Se quitó ${a.nombre} del cierre.`, 'ok', 3000);
        await recargar();
      } catch (err) { avisarError(err); }
    };
    const botonQuitar = a => el('button', { type: 'button', class: 'btn fantasma icono chico quitar-archivo', title: 'Quitar del cierre', 'aria-label': 'Quitar ' + a.nombre,
      onclick: ev => { ev.preventDefault(); ev.stopPropagation(); quitarArchivo(a); } }, icono('i-basura'));
    const subir = async (ent, archivos, barra) => {
      for (const f of archivos) {
        const clave = `subida:${cierre.id}:${f.name}:${f.size}`;
        if (tareas.enCurso(clave)) { aviso(`${f.name} ya se está subiendo; lo ves en Tareas.`, 'info'); continue; }
        const tarea = tareas.iniciar({ clave, titulo: `Subiendo ${f.name}`, detalle: bytesLegibles(f.size), progreso: 0 });
        barra.classList.remove('oculto');
        progresoGlobal(1);
        try {
          const a = await subirArchivo(cierre.id, f, p => {
            barra.firstChild.style.width = Math.round(p * 100) + '%';
            if (p >= 1) tarea.avance(null, 'Reconociendo qué reporte es…'); else tarea.avance(p, `${Math.round(p * 100)}% de ${bytesLegibles(f.size)}`);
          });
          tarea.terminar(a.tipo ? `Reconocí ${tituloTipo(a.tipo)}` + (a.filas != null ? `, ${n(a.filas)} filas.` : '.') : (a.error || 'No reconocí qué reporte es.'), a.tipo ? 'ok' : 'error');
          recienSubidos.add(a.id);
          if (a.tipo === ent.tipo) seleccion[ent.clave].add(a.id);
          else if (a.tipo) aviso(`${a.nombre}: reconocí ${tituloTipo(a.tipo)}, que no es lo que pide esta entrada. Quedó guardado en el cierre por si lo necesitás en otro reporte.`, 'atencion', 9000);
          if (a.aviso) aviso(a.aviso, 'atencion', 12000);
        } catch (err) { tarea.terminar(err.message, 'error'); avisarError(err); }
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
              const agregados = await tareas.correr({ clave: `carpeta:${cierre.id}:${ruta}`, titulo: `Copiando ${nombres.length === 1 ? 'un archivo' : nombres.length + ' archivos'} de la carpeta`, detalle: 'Se copian y se reconocen; los originales no se tocan.' },
                async () => api('POST', `/api/cierres/${encodeURIComponent(cierre.id)}/archivos/desde-carpeta`, { ruta, nombres }));
              if (!agregados) return;
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
        bloque.appendChild(el('div', { class: 'ayuda' }, ent.ayuda || ''));
        const listaArchivos = el('div', { class: 'lista-archivos' });
        bloque.appendChild(listaArchivos);
        // En una versión que ya corrió se ven sólo los archivos que usó; si no, también los del cierre que sirven acá.
        const candidatos = cierre.archivos.filter(a => editable ? a.tipo === ent.tipo || sel.has(a.id) : sel.has(a.id));
        for (const a of candidatos) {
          const detalle = [a.fondo ? (a.fondo === 'mezcla' ? 'mezcla los dos fondos' : `ERP de ${a.fondo}`) : null, a.hoja ? `hoja ${a.hoja}` : null, a.filas != null ? `${n(a.filas)} filas` : null, bytesLegibles(a.bytes), 'agregado ' + fechaCorta(a.subido)].filter(Boolean).join(' · ');
          const casilla = el('input', { type: 'checkbox', checked: sel.has(a.id), disabled: !editable, 'aria-label': 'Usar ' + a.nombre, onchange: ev => { if (ev.target.checked) sel.add(a.id); else sel.delete(a.id); pintar(); } });
          listaArchivos.appendChild(el('label', { class: 'archivo' + (sel.has(a.id) ? ' elegido' : '') + (recienSubidos.has(a.id) ? ' nuevo' : '') }, casilla, el('span', { class: 'icono-archivo' }, icono('i-planilla')),
            el('span', { class: 'datos' }, el('span', { class: 'nombre' }, a.nombre), el('span', { class: 'detalle' }, detalle), a.aviso ? el('span', { class: 'detalle advertencia' }, a.aviso) : null),
            editable ? botonQuitar(a) : null));
        }
        if (editable) {
          for (const a of cierre.archivos.filter(x => !x.tipo && recienSubidos.has(x.id))) {
            listaArchivos.appendChild(el('div', { class: 'archivo problema' }, el('span', { class: 'icono-archivo' }, icono('i-alerta')), el('span', { class: 'datos' }, el('span', { class: 'nombre' }, a.nombre), el('span', { class: 'detalle error' }, a.error ? `No se pudo leer: ${a.error}` : 'No reconocí qué reporte es. Revisá que sea el Excel original descargado del sistema.')),
              btn('Quitar', async () => { try { await api('DELETE', `/api/cierres/${encodeURIComponent(cierre.id)}/archivos/${encodeURIComponent(a.id)}`); recienSubidos.delete(a.id); await recargar(); } catch (err) { avisarError(err); } }, 'fantasma chico', { icono: 'i-basura' })));
          }
          const input = el('input', { type: 'file', multiple: true, accept: '.xlsx,.xlsm', 'aria-label': 'Elegir archivos para ' + ent.titulo });
          const barra = el('div', { class: 'barra-subida oculto' }, el('div', { style: 'width:0' }));
          const zona = el('div', { class: 'zona-soltar' },
            el('div', { class: 'zona-fila' }, el('span', { class: 'icono-subir' }, icono('i-subir')),
              el('div', { class: 'texto' }, el('b', null, candidatos.length ? 'Agregar otro archivo o tramo' : 'Agregar el archivo'), el('span', null, 'Arrastralo acá o elegilo desde la PC'))),
            el('div', { class: 'zona-botones' }, btn('Elegir archivos', () => input.click(), 'chico', { icono: 'i-archivo' }), btn('Desde una carpeta', () => desdeCarpeta(ent), 'fantasma chico', { icono: 'i-carpeta' })), input);
          input.addEventListener('change', () => subir(ent, [...input.files], barra));
          zona.addEventListener('dragover', ev => { ev.preventDefault(); zona.classList.add('sobre'); });
          zona.addEventListener('dragleave', () => zona.classList.remove('sobre'));
          zona.addEventListener('drop', ev => { ev.preventDefault(); zona.classList.remove('sobre'); subir(ent, [...ev.dataTransfer.files], barra); });
          bloque.append(zona, barra);
        }
        if (!listaArchivos.children.length) {
          listaArchivos.appendChild(el('div', { class: 'archivo vacio' }, el('span', { class: 'icono-archivo' }, icono('i-archivo')),
            el('span', { class: 'datos' }, el('span', { class: 'nombre' }, editable ? 'Todavía no hay archivo' : 'Sin archivo'), el('span', { class: 'detalle' }, editable ? 'Agregalo con el recuadro de abajo.' : 'Esta versión no usó archivos acá.'))));
        }
        bloques.appendChild(bloque);
      }
      // Archivos del cierre que no son de ningún reporte conocido (por ejemplo, un Excel exportado): se pueden quitar.
      const sueltos = editable ? cierre.archivos.filter(a => !a.tipo && !recienSubidos.has(a.id)) : [];
      if (sueltos.length) {
        bloques.appendChild(el('details', { class: 'avanzadas archivos-sueltos' },
          el('summary', null, icono('i-alerta'), el('span', null, `Archivos del cierre que no reconocí (${sueltos.length}) `, el('span', { class: 'muted' }, 'no sirven para ningún reporte; podés quitarlos')), icono('i-abajo', 'flecha')),
          el('div', { class: 'contenido' }, sueltos.map(a => el('div', { class: 'archivo problema' }, el('span', { class: 'icono-archivo' }, icono('i-alerta')),
            el('span', { class: 'datos' }, el('span', { class: 'nombre' }, a.nombre), el('span', { class: 'detalle' }, [bytesLegibles(a.bytes), 'agregado ' + fechaCorta(a.subido)].join(' · '))),
            btn('Quitar', () => quitarArchivo(a), 'fantasma chico', { icono: 'i-basura' }))))));
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
    // El fondo (la variante): al cambiarlo, la versión pasa a la serie de ese fondo y el encabezado lo muestra.
    const alCambiarVariante = p => reporte.variantes && p.clave === reporte.variantes.parametro ? async () => {
      try { estado.w.e = await api('PATCH', '/api/ejecuciones/' + encodeURIComponent(e.id), { parametros: valores }); await vistaEjecucion(e.id, '2', true); } catch (err) { avisarError(err); }
    } : null;
    if (principales.length) form.appendChild(el('div', { class: 'grupo-opciones' }, principales.map(p => campoParametro(p, valores, editable, propuestas, alCambiarVariante(p)))));
    // El fondo se valida acá, donde se elige: el ERP elegido en Archivos tiene que ser de ese fondo (se reconoce por sus
    // asientos al agregarlo al cierre).
    const conflicto = (() => {
      if (!editable || !reporte.variantes) return null;
      const fondo = valores[reporte.variantes.parametro];
      const archivos = Object.fromEntries((cierre.archivos || []).map(a => [a.id, a]));
      const malo = Object.values(e.entradas || {}).flat().map(i => archivos[i]).find(a => a && a.fondo && a.fondo !== fondo);
      return malo ? { archivo: malo, fondo } : null;
    })();
    if (conflicto) {
      const { archivo, fondo } = conflicto;
      const usarFondo = () => { const s = $('#par-' + reporte.variantes.parametro); s.value = archivo.fondo; s.dispatchEvent(new Event('change')); };
      form.appendChild(el('div', { class: 'caja-error conflicto-fondo' }, icono('i-alerta'),
        el('div', null, el('p', null, el('b', null, 'El ERP no es de este fondo. '),
          archivo.fondo === 'mezcla' ? `${archivo.nombre}, elegido en Archivos, mezcla movimientos de los dos fondos.` : `${archivo.nombre}, elegido en Archivos, es de ${archivo.fondo} y el fondo elegido es ${fondo}.`),
          el('div', { class: 'acciones-fila' }, archivo.fondo !== 'mezcla' ? btn(`Usar ${archivo.fondo}`, usarFondo, 'chico', { icono: 'i-caja' }) : null,
            btn('Elegir otro ERP', () => { location.hash = `#/ejecucion/${encodeURIComponent(e.id)}/1`; }, 'fantasma chico', { icono: 'i-izq' })))));
    }
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
        }, 'primario grande llama', { icono: 'i-play', disabled: !!conflicto, title: conflicto ? 'Primero resolvé el aviso del fondo de riesgo' : null })));
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
  function campoParametro(p, valores, editable, propuestas, alCambiar = null) {
    const id = 'par-' + p.clave;
    // Las opciones de pocas alternativas y las rutas ocupan dos columnas; las listas y tablas, el ancho entero.
    const ancho = p.tipo === 'tabla' || p.tipo === 'lista' || (p.tipo === 'opcion' && (p.opciones || []).length > 3);
    const doble = !ancho && (p.tipo === 'opcion' || p.tipo === 'ruta');
    const campo = el('div', { class: 'campo' + (ancho ? ' ancho' : doble ? ' doble' : '') });
    const v = valores[p.clave];
    const fijar = x => { valores[p.clave] = x; };
    const rotulo = texto => el('div', { class: 'rotulo' }, texto + (p.obligatorio ? ' *' : ''));
    if (p.tipo === 'fecha' || p.tipo === 'texto' || p.tipo === 'ruta' || p.tipo === 'decimal') {
      campo.append(el('label', { for: id }, p.titulo + (p.obligatorio ? ' *' : '')), el('input', { type: p.tipo === 'fecha' ? 'date' : 'text', id, value: v == null ? '' : String(v), disabled: !editable, required: !!p.obligatorio, oninput: ev => fijar(ev.target.value) }));
    } else if (p.tipo === 'opcion' && p.desplegable) {
      campo.append(el('label', { for: id }, p.titulo + (p.obligatorio ? ' *' : '')),
        el('select', { id, class: 'selector', disabled: !editable, onchange: ev => { fijar(ev.target.value); if (alCambiar) alCambiar(ev.target.value); } },
          p.opciones.map(o => el('option', { value: o.valor, text: o.titulo, selected: valores[p.clave] === o.valor }))));
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
        try { const t2 = await api('GET', '/api/trabajos/' + e.trabajoId, undefined, { silencioso: true }); pintarTrabajo(t2); if (!(t2.estado === 'corriendo' || t2.estado === 'esperando')) detenerSondeo(); } catch (err) { /* próxima vuelta */ }
      }, 1500);
    }
  }
  function pintarTrabajo(t) {
    const w = estado.w;
    if (!w || !w.nodos || w.paso !== 3) return;
    const anterior = w.trabajo;
    w.trabajo = t;
    const nodos = w.nodos;
    const { iconoEstado, titulo, pasoActual, pista, porcentaje, zonaEspera, lineaTiempo, consola, pie } = nodos;
    const activo = t.estado === 'corriendo' || t.estado === 'esperando';
    const cambioEstado = !anterior || anterior.estado !== t.estado;
    if (cambioEstado) {
      const ic = { corriendo: 'i-play', esperando: 'i-mano', ok: 'i-check', error: 'i-alerta', cancelado: 'i-detener', interrumpido: 'i-alerta' }[t.estado] || 'i-reloj';
      iconoEstado.className = 'icono-estado ' + ({ corriendo: 'girando', esperando: 'espera', ok: 'ok', error: 'error', interrumpido: 'error' }[t.estado] || '');
      limpiar(iconoEstado).appendChild(icono(ic));
    }
    ponerTexto(titulo, { ok: 'Terminó bien', error: 'Terminó con un error', cancelado: 'Se canceló', interrumpido: 'Se interrumpió', esperando: 'Necesita una acción tuya' }[t.estado] || 'Corriendo…');
    ponerTexto(pasoActual, activo ? (t.paso && t.paso !== 'Arrancando' ? t.paso : 'Preparando…') : t.estado === 'ok' ? 'Los resultados ya están listos para revisar.' : '');
    pista.parentElement.classList.toggle('oculto', !activo && t.estado !== 'ok');
    pista.classList.toggle('indeterminada', activo && !(t.progreso > 0));
    const ancho = Math.round((t.estado === 'ok' ? 1 : (t.progreso || 0)) * 100) + '%';
    if (pista.firstChild.style.width !== ancho) pista.firstChild.style.width = ancho;
    ponerTexto(porcentaje, t.estado === 'ok' ? '100%' : t.progreso > 0 ? Math.round(t.progreso * 100) + '%' : '');
    // Línea de tiempo: los pasos que ya están quedan como están; sólo entran los nuevos (con su animación).
    const lineas = t.lineas || [];
    const pasos = [...new Set(lineas.filter(l => l.startsWith('== ')).map(l => l.slice(3)))];
    const items = lineaTiempo.children;
    pasos.forEach((p, i) => {
      const actual = activo && i === pasos.length - 1;
      let li = items[i];
      if (!li || li.dataset.paso !== p) {
        while (items.length > i) lineaTiempo.lastChild.remove();
        li = el('li', { 'data-paso': p }, el('span', { class: 'marca-paso' }), el('span', null, p));
        lineaTiempo.appendChild(li);
      }
      const clase = actual ? 'actual' : 'hecho';
      if (li.className !== clase) {
        li.className = clase;
        limpiar(li.firstChild);
        if (!actual) li.firstChild.appendChild(icono('i-check'));
      }
    });
    while (items.length > pasos.length) lineaTiempo.lastChild.remove();
    // Detalle técnico: se agregan sólo las líneas nuevas.
    const mostradas = nodos.lineas || [];
    const continua = mostradas.length > 0 && lineas.length >= mostradas.length && lineas[0] === mostradas[0] && lineas[mostradas.length - 1] === mostradas[mostradas.length - 1];
    const abajo = consola.scrollHeight - consola.scrollTop - consola.clientHeight < 30;
    if (!continua) limpiar(consola);
    for (const l of (continua ? lineas.slice(mostradas.length) : lineas.slice(-400))) consola.appendChild(el('div', null, l));
    while (consola.children.length > 400) consola.firstChild.remove();
    if (t.error && nodos.errorMostrado !== t.error) { nodos.errorMostrado = t.error; consola.appendChild(el('div', null, t.error)); }
    const ultima = consola.querySelector('.ultima');
    if (ultima !== consola.lastChild) { if (ultima) ultima.classList.remove('ultima'); if (consola.lastChild) consola.lastChild.classList.add('ultima'); }
    if (abajo || !continua) consola.scrollTop = consola.scrollHeight;
    nodos.lineas = lineas.slice();
    // Caja de espera, error u ok: sólo cuando cambia el estado (o la espera).
    const claveZona = `${t.estado}|${t.espera ? t.espera.id : ''}|${t.error || ''}`;
    if (nodos.claveZona !== claveZona) {
      nodos.claveZona = claveZona;
      limpiar(zonaEspera);
      if (t.estado === 'esperando' && t.espera) {
        zonaEspera.appendChild(el('div', { class: 'caja-espera' }, icono('i-mano', 'xg'), el('p', null, t.espera.mensaje),
          btn(t.espera.boton || 'Continuar', async () => { try { await api('POST', `/api/trabajos/${t.id}/continuar`, { espera: t.espera.id }); } catch (err) { avisarError(err); } }, 'primario grande', { icono: 'i-play' })));
      } else if ((t.estado === 'error' || t.estado === 'interrumpido') && t.error) {
        zonaEspera.appendChild(el('div', { class: 'caja-error' }, icono('i-alerta'), el('div', null, el('p', null, el('b', null, 'Qué pasó: '), t.error), el('p', { class: 'muted' }, 'Corregí lo que indica el mensaje y volvé a correr. Si no se entiende, copiá el detalle técnico para pedir ayuda.'))));
      } else if (t.estado === 'ok') {
        const tablas = Object.entries(t.tablas || {});
        zonaEspera.appendChild(el('div', { class: 'caja-ok' }, icono('i-check-circulo'), el('p', null, tablas.length ? `Se generaron ${tablas.length === 1 ? 'una tabla' : tablas.length + ' tablas'} con ${n(tablas.reduce((s, [, f]) => s + f, 0))} filas para revisar.` : 'El reporte terminó.')));
      }
    }
    if (!cambioEstado && nodos.pieListo) return;
    nodos.pieListo = true;
    limpiar(pie);
    const e = w.e;
    if (activo) {
      pie.append(el('div', { class: 'izq' }, el('span', { class: 'muted' }, 'Podés cerrar esta pestaña o seguir con otra cosa: el reporte sigue corriendo y lo ves en Tareas.')),
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
  // Filtros de revisión de la grilla. "Para revisar" sólo existe en las tablas con regla (por ejemplo, Resultado distinto
  // de COINCIDE): son las filas que cuentan en el medidor, en cualquier estado.
  const ESTADOS_GRILLA = [['revisar', 'Para revisar'], ['', 'Todas'], ['pendiente', 'Pendientes'], ['revisada', 'Revisadas'], ['omitida', 'Omitidas']];
  function grillaInicial(t, cantidad) {
    return { tabla: t ? t.tabla : null, desde: 0, cantidad: cantidad || 100, orden: null, desc: false, filtro: '', columna: '',
      estado: t && t.revisar ? 'revisar' : '', filtros: {}, condiciones: {}, seleccion: new Set() };
  }
  // Consulta de la grilla para el servidor. `sin`: deja afuera el filtro de esa columna (la lista de valores de un
  // filtro de encabezado se calcula con los demás filtros, como en Excel).
  function consultaGrilla(g, sin = null) {
    const q = new URLSearchParams({ filtro: g.filtro || '', columna: g.columna || '' });
    if (g.estado === 'revisar') q.set('requiere', '1'); else if (g.estado) q.set('estado', g.estado);
    if (g.orden) { q.set('orden', g.orden); q.set('desc', g.desc ? '1' : '0'); }
    const filtros = { ...(g.filtros || {}) };
    const condiciones = { ...(g.condiciones || {}) };
    if (sin) { delete filtros[sin]; delete condiciones[sin]; }
    if (Object.keys(filtros).length) q.set('filtros', JSON.stringify(filtros));
    if (Object.keys(condiciones).length) q.set('condiciones', JSON.stringify(condiciones));
    return q;
  }
  const importeLegible = x => Number(x).toLocaleString('es-AR', { maximumFractionDigits: 2 });
  // Lee un importe escrito como en Excel: "-1.500,50", "1500.5", "3000000".
  function leerImporte(texto) {
    let t = String(texto || '').trim().replace(/\s/g, '');
    if (!t) return null;
    if (t.includes(',')) t = t.replace(/\./g, '').replace(',', '.');
    else if (/^-?\d{1,3}(\.\d{3})+$/.test(t)) t = t.replace(/\./g, '');
    const v = Number(t);
    return Number.isFinite(v) ? v : null;
  }

  // Ventana del filtro de encabezado. Va en el body (posición fija) y se cierra al hacer clic afuera, con Escape,
  // al desplazar la página o al cambiar de vista.
  let popoverFiltro = null;
  function cerrarPopoverFiltro() {
    if (!popoverFiltro) return;
    const p = popoverFiltro;
    popoverFiltro = null;
    document.removeEventListener('mousedown', p._fuera, true);
    document.removeEventListener('keydown', p._esc, true);
    window.removeEventListener('scroll', p._scroll, true);
    window.removeEventListener('resize', p._scroll);
    p.classList.add('saliendo');
    setTimeout(() => p.remove(), 130);
  }
  function abrirPopoverFiltro(ancla, contenido, columna, etiqueta) {
    cerrarPopoverFiltro();
    const p = el('div', { class: 'popover-filtro', role: 'dialog', 'aria-label': etiqueta || 'Filtro de ' + columna }, contenido);
    p.dataset.columna = columna;
    p._fuera = ev => { if (!p.contains(ev.target) && !ev.target.closest('.boton-filtro, .en-buscador')) cerrarPopoverFiltro(); };
    p._esc = ev => { if (ev.key === 'Escape') { ev.stopPropagation(); cerrarPopoverFiltro(); } };
    const abierto = Date.now();
    p._scroll = ev => { if (Date.now() - abierto < 300) return; if (!ev || !ev.target || !(ev.target instanceof Node) || !p.contains(ev.target)) cerrarPopoverFiltro(); };
    document.body.appendChild(p);
    const reubicar = () => {
      const r = ancla.getBoundingClientRect();
      p.style.left = Math.max(8, Math.min(window.innerWidth - p.offsetWidth - 8, r.left)) + 'px';
      let arriba = r.bottom + 6;
      if (arriba + p.offsetHeight > window.innerHeight - 8) arriba = Math.max(8, Math.min(r.top - p.offsetHeight - 6, window.innerHeight - p.offsetHeight - 8));
      p.style.top = arriba + 'px';
    };
    reubicar();
    document.addEventListener('mousedown', p._fuera, true);
    document.addEventListener('keydown', p._esc, true);
    window.addEventListener('scroll', p._scroll, true);
    window.addEventListener('resize', p._scroll);
    popoverFiltro = p;
    return { p, reubicar };
  }
  const OPERACIONES_NUMERO = [['distinto_cero', 'Distinto de cero'], ['igual', 'Igual a'], ['mayor', 'Mayor que'], ['menor', 'Menor que'], ['entre', 'Entre']];
  const textoRegla = r => r ? `${r.columna} ${r.salvo.join(' o ')}` : '';

  // Vista de columnas de una tabla: la guardada en Configuración, o la que propone el reporte (`vista` de la salida).
  function vistaColumnas(w, info) {
    const todas = info.columnas;
    const guardada = (((estado.conf || {}).vistas || {})[w.reporte.codigo] || {})[info.tabla];
    let orden, ocultas;
    if (guardada) {
      orden = guardada.orden.filter(c => todas.includes(c));
      // Una columna nueva del reporte va delante de la que la sigue en el orden del reporte, no al final.
      todas.forEach((c, i) => {
        if (orden.includes(c)) return;
        const siguiente = todas.slice(i + 1).find(x => orden.includes(x));
        orden.splice(siguiente ? orden.indexOf(siguiente) : orden.length, 0, c);
      });
      ocultas = new Set(guardada.ocultas.filter(c => todas.includes(c)));
    } else {
      const def = info.vista || {};
      const primero = (def.primero || []).filter(c => todas.includes(c));
      orden = [...primero, ...todas.filter(c => !primero.includes(c))];
      ocultas = new Set((def.ocultas || []).filter(c => todas.includes(c)));
    }
    return { orden, ocultas, visibles: orden.filter(c => !ocultas.has(c)), personalizada: !!guardada };
  }
  async function guardarVista(w, info, vista) {
    const valor = vista ? { orden: vista.orden, ocultas: [...vista.ocultas] } : null;
    estado.conf = await api('PATCH', '/api/configuracion', { vistas: { [w.reporte.codigo]: { [info.tabla]: valor } } });
  }
  function configurarColumnas(w, info, alGuardar) {
    const actual = vistaColumnas(w, info);
    const orden = [...actual.orden];
    const ocultas = new Set(actual.ocultas);
    const lista = el('ul', { class: 'lista-columnas' });
    const resumen = el('p', { class: 'muted', style: 'margin:0 0 10px' });
    let arrastrada = null;
    const cuenta = () => { resumen.textContent = `Se ven ${n(orden.length - ocultas.size)} de ${n(orden.length)} columnas. Arriba es más a la izquierda; arrastralas o usá las flechas.`; };
    const mover = (desde, hasta) => {
      if (hasta < 0 || hasta >= orden.length || desde === hasta) return;
      const [c] = orden.splice(desde, 1);
      orden.splice(hasta, 0, c);
      pintar();
      const fila = lista.children[hasta];
      if (fila) { fila.classList.add('movida'); fila.scrollIntoView({ block: 'nearest' }); }
    };
    const pintar = () => {
      limpiar(lista);
      orden.forEach((c, i) => {
        const casilla = el('input', { type: 'checkbox', checked: !ocultas.has(c), onchange: ev => { if (ev.target.checked) ocultas.delete(c); else ocultas.add(c); li.classList.toggle('oculta', !ev.target.checked); cuenta(); } });
        const li = el('li', { draggable: 'true', class: ocultas.has(c) ? 'oculta' : '' },
          el('span', { class: 'agarre', title: 'Arrastrá para mover' }, icono('i-agarrar')),
          el('label', { class: 'casilla' }, casilla, el('span', null, c)),
          el('span', { class: 'mover' },
            btn('', () => mover(i, i - 1), 'fantasma icono chico', { icono: 'i-arriba', aria: `Mover ${c} a la izquierda`, title: 'Más a la izquierda', disabled: i === 0 }),
            btn('', () => mover(i, i + 1), 'fantasma icono chico', { icono: 'i-abajo', aria: `Mover ${c} a la derecha`, title: 'Más a la derecha', disabled: i === orden.length - 1 })));
        li.addEventListener('dragstart', ev => { arrastrada = i; li.classList.add('arrastrando'); ev.dataTransfer.effectAllowed = 'move'; ev.dataTransfer.setData('text/plain', c); });
        li.addEventListener('dragend', () => li.classList.remove('arrastrando'));
        li.addEventListener('dragover', ev => { ev.preventDefault(); li.classList.add('destino'); });
        li.addEventListener('dragleave', () => li.classList.remove('destino'));
        li.addEventListener('drop', ev => { ev.preventDefault(); li.classList.remove('destino'); if (arrastrada !== null) mover(arrastrada, i); arrastrada = null; });
        lista.appendChild(li);
      });
      cuenta();
    };
    const { cerrar } = abrirModal({ titulo: 'Columnas de la tabla', iconoNombre: 'i-columnas',
      cuerpo: el('div', null, el('p', { style: 'margin-top:0' }, `Elegí qué columnas ver en "${info.titulo}" y en qué orden. La vista queda guardada para este reporte y Exportar puede usarla.`), resumen, lista),
      pie: [btn('Restablecer', async () => { try { await guardarVista(w, info, null); cerrar(); aviso('Volvió la vista original de la tabla.', 'info', 3000); alGuardar(); } catch (err) { avisarError(err); } }, 'fantasma', { icono: 'i-deshacer', title: 'Volver a la vista que propone el reporte' }),
        btn('Mostrar todas', () => { ocultas.clear(); pintar(); }, 'fantasma', { icono: 'i-ojo' }),
        el('span', { style: 'flex:1' }),
        btn('Cancelar', () => cerrar()),
        btn('Guardar', async () => {
          if (ocultas.size >= orden.length) { aviso('Dejá al menos una columna a la vista.', 'atencion'); return; }
          try { await guardarVista(w, info, { orden, ocultas }); cerrar(); aviso('Vista guardada.', 'ok', 2500); alGuardar(); } catch (err) { avisarError(err); }
        }, 'primario', { icono: 'i-check' })] });
    pintar();
  }

  // Descarga con aviso de error en pantalla (no navega a una página de error) y la barra de carga arriba.
  async function descargar(ruta, titulo = 'Descarga', detalle = 'Armando el archivo…') {
    return tareas.correr({ clave: 'descarga:' + ruta, titulo, detalle }, async () => {
      let r;
      try { r = await fetch(ruta, { credentials: 'same-origin' }); } catch (e) { throw new Error('No se pudo hablar con la herramienta. Si la cerraste, volvé a abrirla desde su acceso directo.'); }
      if (!r.ok) {
        let mensaje = `Error ${r.status}`;
        try { mensaje = (await r.json()).error || mensaje; } catch (e) { /* sin detalle */ }
        const err = new Error(mensaje); err.status = r.status; throw err;
      }
      const blob = await r.blob();
      const m = /filename\*=UTF-8''([^;]+)/i.exec(r.headers.get('Content-Disposition') || '');
      const nombre = m ? decodeURIComponent(m[1]) : 'descarga.xlsx';
      const url = URL.createObjectURL(blob);
      const a = el('a', { href: url, download: nombre, style: 'display:none' });
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 60000);
      return 'Descargado: ' + nombre;
    }, `Ya se está armando: ${titulo}. Te aviso cuando esté; lo ves en Tareas.`);
  }

  // Excel de origen de una fila: la primera vez espera a que estén las copias de consulta de los Excel de entrada.
  const origenPendiente = new Map();  // ejecución -> fila cuyo Excel de origen se baja apenas esté la copia
  async function excelDeOrigen(e, tabla, fila, comprobante) {
    const base = `/api/ejecuciones/${encodeURIComponent(e.id)}/origen`;
    const bajar = () => descargar(`${base}?tabla=${encodeURIComponent(tabla)}&fila=${encodeURIComponent(fila)}`, `Excel de origen${comprobante ? ' de ' + comprobante : ''}`, 'Filas de SGA y ERP que forman la fila.');
    try {
      let st = await api('GET', base + '/estado');
      if (!st.listo) {
        if (!st.preparando) st = await api('POST', base + '/preparar', {});
        if (st.error) { aviso(st.error, 'error', 9000); return; }
        const espera = st.listo ? 'listo' : await esperarOrigen(base);
        if (espera === 'error') return;
        if (espera === 'seguir') {
          origenPendiente.set(e.id, bajar);
          aviso('Se sigue preparando. Cuando esté, el Excel se baja solo; el avance está en Tareas.', 'info', 6000);
          return;
        }
      }
      await bajar();
    } catch (err) { avisarError(err); }
  }
  function esperarOrigen(base) {
    return new Promise(resolve => {
      const relleno = el('div');
      const barra = el('div', { class: 'barra-progreso' }, relleno);
      const texto = el('p', { class: 'muted', style: 'margin:8px 0 0' }, 'Empezando…');
      let terminado = false;
      let reloj = null;
      const { cerrar } = abrirModal({ titulo: 'Preparando el Excel de origen', iconoNombre: 'i-planilla',
        cuerpo: el('div', null, el('p', { style: 'margin-top:0' }, 'La primera vez, la herramienta pasa los Excel de entrada a un formato de consulta rápida. Tarda alrededor de un minuto por cada 60 MB. Después, cada Excel de origen sale al instante.'), barra, texto),
        pie: [btn('Seguir trabajando', () => cerrar(), 'primario')],
        alCerrar: () => { clearTimeout(reloj); if (!terminado) { terminado = true; resolve('seguir'); } } });
      // 'listo': ya se puede bajar; 'seguir': el usuario siguió trabajando; 'error': no se pudo preparar.
      const fin = r => { terminado = true; clearTimeout(reloj); cerrar(); resolve(r); };
      const mirar = async () => {
        try {
          const st = await api('GET', base + '/estado');
          if (st.listo) return fin('listo');
          if (st.error) { fin('error'); aviso(st.error, 'error', 9000); return; }
          const pct = Math.round((st.progreso || 0) * 100);
          relleno.style.width = pct + '%';
          texto.textContent = `${pct}% preparado`;
        } catch (err) { fin('error'); avisarError(err); return; }
        if (!terminado) reloj = setTimeout(mirar, 900);
      };
      mirar();
    });
  }

  async function pasoResultados(cont, w) {
    const { e } = w;
    const datos = await api('GET', `/api/ejecuciones/${encodeURIComponent(e.id)}/tablas`);
    w.tablas = datos.tablas;
    if (!datos.tablas.length) { cont.appendChild(intro('i-info', 'El reporte terminó pero no dejó tablas para revisar. Sus archivos están en el paso Exportar.')); return; }
    const revisables = () => w.tablas.filter(t => t.revisable !== false);
    const elegir = t => { w.tabla = t.tabla; w.grilla = grillaInicial(t, w.grilla && w.grilla.cantidad); };
    if (!w.tabla || !datos.tablas.some(t => t.tabla === w.tabla)) w.tabla = (datos.tablas.find(t => t.principal) || revisables().find(t => t.estados.pendiente > 0) || datos.tablas[0]).tabla;
    if (!w.grilla || w.grilla.tabla !== w.tabla) elegir(datos.tablas.find(t => t.tabla === w.tabla));
    if (datos.tablas.some(t => t.origen)) api('POST', `/api/ejecuciones/${encodeURIComponent(e.id)}/origen/preparar`, {}).catch(() => {});
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
      const sinRevisar = revisables().reduce((a, t) => a + Math.max(0, t.filas - (t.aRevisar == null ? t.filas : t.aRevisar)), 0);
      const reglas = [...new Set(revisables().filter(t => t.revisar && t.filas > t.aRevisar).map(t => textoRegla(t.revisar)))];
      const pct = total ? Math.round((tot.r + tot.o) / total * 100) : 100;
      limpiar(medidor).append(el('div', { class: 'cifra' }, `${pct}%`, el('br'), el('small', null, 'revisado')),
        el('div', { class: 'medidor' }, el('b', null, tot.p ? (tot.p === 1 ? 'Te falta una fila por revisar' : `Te faltan ${n(tot.p)} filas por revisar`) : 'Revisaste todo'),
          barraRevision({ pendientes: tot.p, revisadas: tot.r, omitidas: tot.o }),
          el('div', { class: 'leyenda-revision' }, el('span', null, el('b', null, n(tot.r)), ' revisadas'), el('span', null, el('b', null, n(tot.o)), ' omitidas'), el('span', null, el('b', null, n(tot.p)), ' pendientes')),
          sinRevisar ? el('div', { class: 'nota-medidor' }, icono('i-check-circulo'), el('span', null, `${n(sinRevisar)} ${sinRevisar === 1 ? 'fila da' : 'filas dan'} ${reglas.join(' / ')} y no hace falta revisarlas. Están en la grilla con el filtro Todas.`)) : null),
        el('div', { class: 'acciones-fila' }, btn('Traer la revisión del cierre anterior', traerAnterior, 'fantasma chico', { icono: 'i-deshacer' }), btn('Exportar', () => { location.hash = `#/ejecucion/${encodeURIComponent(e.id)}/5`; }, 'chico', { icono: 'i-bajar' })));
      return tot;
    };
    const traerAnterior = async () => {
      if (!await confirmar('¿Traer la revisión del cierre anterior?', 'Se marcan como omitidas, con su observación, las filas que en el cierre anterior se omitieron y que acá siguen pendientes. Las revisadas no se traen: son de ese mes.', 'Traer', 'pregunta')) return;
      try { const r = await api('POST', `/api/ejecuciones/${encodeURIComponent(e.id)}/traer-revision-anterior`, {}); aviso(r.desde ? `Del cierre de ${periodoLargo(r.desde)}: ${n(r.aplicadas)} filas marcadas${r.sin_destino ? `, ${n(r.sin_destino)} sin fila en este mes` : ''}.` : 'No hay un cierre anterior con este reporte.', r.desde ? 'ok' : 'atencion'); await pasoResultados(limpiar(cont), w); } catch (err) { avisarError(err); }
    };
    cont.appendChild(intro('i-tabla', 'Marcá cada fila como revisada u omitida y anotá observaciones. Lo que marques se guarda solo y pasa a la próxima versión de este mes.'));
    if (datos.tablas.some(t => t.anterior)) cont.appendChild(el('div', { class: 'caja-espera version-anterior', style: 'margin:0 0 16px' }, icono('i-alerta', 'g'),
      el('p', null, el('b', null, 'Esta versión es de antes de un cambio del reporte.'), ` Algunas tablas se ven como eran entonces (${datos.tablas.filter(t => t.anterior).map(t => t.hoja || t.titulo).join(', ')}). Corré una versión nueva con los mismos archivos y opciones para verlas como ahora: lo que ya revisaste pasa solo.`),
      btn('Correr una versión nueva', correrNuevaVersion(w), 'primario', { icono: 'i-play' })));
    if (datos.traslado && datos.traslado.desde) cont.appendChild(el('div', { class: 'caja-info', style: 'margin:0 0 14px' }, icono('i-deshacer'), el('p', null, `De la versión ${datos.traslado.desde} se trasladaron ${n(datos.traslado.aplicadas)} marcas` + (datos.traslado.sin_destino ? `; ${n(datos.traslado.sin_destino)} no encontraron su fila en esta versión.` : '.'))));
    cont.appendChild(medidor);
    pintarMedidor();
    setTimeout(() => medidor.classList.add('quieta'), 900);
    if (datos.resumen && typeof datos.resumen === 'object') {
      const grillaResumen = el('div', { class: 'tarjeta resumen-motor' });
      for (const [k, v] of Object.entries(datos.resumen)) {
        if (v && typeof v === 'object' && !Array.isArray(v)) { for (const [k2, v2] of Object.entries(v)) if (typeof v2 !== 'object' || v2 === null) grillaResumen.appendChild(el('div', null, el('span', null, `${k} · ${k2}`), el('span', { title: String(v2) }, String(v2)))); }
        else if (!Array.isArray(v)) grillaResumen.appendChild(el('div', null, el('span', null, k), el('span', { title: String(v) }, String(v))));
      }
      cont.appendChild(el('details', { class: 'resumen-corrida' }, el('summary', null, icono('i-info'), 'Resumen de la corrida', icono('i-abajo', 'flecha')), grillaResumen));
    }
    const cuerpo = el('div', { class: 'resultados' });
    const lista = el('nav', { class: 'tarjeta lista-tablas', 'aria-label': 'Tablas del reporte' });
    const derecha = el('div');
    cuerpo.append(lista, derecha);
    cont.appendChild(cuerpo);
    // Secciones abiertas o cerradas por el usuario (mientras dure la pantalla); sin elección, se abre la de la tabla activa.
    if (!w.secciones) w.secciones = new Map();
    const nombreLibro = archivo => String(archivo).replace(/\.(xlsx|csv|txt)$/i, '').split('_').filter(Boolean)
      .map((p, i) => i === 0 ? p.charAt(0).toUpperCase() + p.slice(1) : (p.length > 1 && p === p.toUpperCase() ? p : p.toLowerCase())).join(' ');
    const pintarLista = () => {
      limpiar(lista);
      const boton = (t, hija) => el('button', { type: 'button', class: (t.tabla === w.tabla ? 'activa' : '') + (hija ? ' hija' : ''), 'aria-current': t.tabla === w.tabla ? 'true' : null, title: t.titulo,
        onclick: () => { if (t.tabla === w.tabla) return; elegir(t); pintarLista(); grilla(derecha, w, alCambiar); } },
        icono(t.revisable === false ? 'i-info' : 'i-tabla'), el('span', { class: 'nombre' }, hija && t.hoja ? t.hoja : t.titulo),
        t.revisable === false ? el('span', { class: 'muted', style: 'font-size:12px' }, n(t.filas)) :
          el('span', { class: 'pend' + (t.estados.pendiente ? '' : ' cero'), title: `${n(t.estados.pendiente)} pendientes de ${n(t.aRevisar == null ? t.filas : t.aRevisar)} para revisar` }, t.estados.pendiente ? n(t.estados.pendiente) : '✓'));
      const libros = [];
      for (const t of revisables()) {
        const clave = t.seccion || t.archivo || t.tabla;
        let l = libros.find(x => x.clave === clave);
        if (!l) libros.push(l = { clave, titulo: t.seccion || nombreLibro(clave), seccion: !!t.seccion, tablas: [] });
        l.tablas.push(t);
      }
      for (const l of libros) {
        // Un libro de una sola tabla va suelto, salvo que el reporte le dé título de sección (Comprobantes abiertos).
        if (libros.length === 1 || (l.tablas.length === 1 && !l.seccion)) { for (const t of l.tablas) lista.appendChild(boton(t, false)); continue; }
        const conActiva = l.tablas.some(t => t.tabla === w.tabla);
        let abierta = w.secciones.has(l.clave) ? w.secciones.get(l.clave) : conActiva;
        const pendientes = l.tablas.reduce((a, t) => a + t.estados.pendiente, 0);
        const hijos = el('div', { class: 'seccion-hijos' + (abierta ? ' abierta' : '') }, el('div', null, l.tablas.map(t => boton(t, true))));
        const cabeza = el('button', { type: 'button', class: 'seccion-tablas' + (abierta ? ' abierta' : '') + (conActiva ? ' con-activa' : ''), 'aria-expanded': String(abierta), title: l.titulo,
          onclick: () => {
            abierta = !abierta;
            w.secciones.set(l.clave, abierta);
            cabeza.classList.toggle('abierta', abierta);
            cabeza.setAttribute('aria-expanded', String(abierta));
            hijos.classList.toggle('abierta', abierta);
          } },
          icono('i-abajo', 'flecha'), el('span', { class: 'nombre' }, l.titulo),
          el('span', { class: 'pend' + (pendientes ? '' : ' cero'), title: `${n(pendientes)} pendientes en esta sección` }, pendientes ? n(pendientes) : '✓'));
        lista.append(cabeza, hijos);
      }
      const info = w.tablas.filter(t => t.revisable === false);
      if (info.length) {
        lista.appendChild(el('div', { class: 'libro' }, 'Información'));
        for (const t of info) lista.appendChild(boton(t, false));
      }
    };
    let todoRevisado = revisables().every(t => !t.estados.pendiente);
    const alCambiar = () => {
      pintarLista();
      const tot = pintarMedidor();
      if (!todoRevisado && tot.p === 0 && revisables().length) { todoRevisado = true; aviso('Revisaste todas las filas. Podés exportar el Excel trabajado y marcar esta versión como resultado final.', 'ok', 8000); }
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
  // Mientras se vuelve a armar un bloque cuyos datos llegan después, conserva su alto: si no, la página se acorta y
  // vuelve a crecer (y con el scroll abajo, el encabezado se agranda y se achica): se ve como un salto o una vibración.
  function conservarAlto(cont) {
    const alto = cont.offsetHeight;
    if (alto) cont.style.minHeight = alto + 'px';
    return () => requestAnimationFrame(() => { cont.style.minHeight = ''; });
  }
  async function grilla(cont, w, alCambiar) {
    const soltar = conservarAlto(cont);
    try { await armarGrilla(cont, w, alCambiar); } finally { soltar(); }
  }
  async function armarGrilla(cont, w, alCambiar) {
    const g = w.grilla;
    const e = w.e;
    const info = w.tablas.find(t => t.tabla === w.tabla);
    const revisable = info.revisable !== false;
    const conOrigen = revisable && !!info.origen;
    if (!revisable) g.estado = '';
    if (g.estado === 'revisar' && !info.revisar) g.estado = '';
    let vista = vistaColumnas(w, info);
    let pagina = null;
    if (!g.filtros) g.filtros = {};
    if (!g.condiciones) g.condiciones = {};
    cerrarPopoverFiltro();
    limpiar(cont);
    const buscar = el('input', { type: 'search', placeholder: 'Buscar…', title: 'Buscar en esta tabla', value: g.filtro, 'aria-label': 'Buscar en esta tabla' });
    let temporizador = null;
    buscar.addEventListener('input', () => { clearTimeout(temporizador); temporizador = setTimeout(() => { g.filtro = buscar.value; g.desde = 0; cargar(); }, 350); });
    const etiquetaColumna = () => g.columna || 'En todas';
    const columna = el('button', { type: 'button', class: 'en-buscador', 'aria-haspopup': 'listbox', title: 'Buscar sólo en una columna', onclick: ev => { ev.stopPropagation(); elegirColumna(); } },
      el('span', { class: 'texto' }, etiquetaColumna()), icono('i-abajo'));
    const elegirColumna = () => {
      if (popoverFiltro && popoverFiltro.dataset.columna === '__columna') { cerrarPopoverFiltro(); return; }
      const muchas = info.columnas.length > 8;
      const filtroTexto = el('input', { type: 'search', class: 'entrada-texto', placeholder: 'Buscar una columna…', 'aria-label': 'Buscar una columna' });
      const opciones = el('div', { class: 'pf-lista lista-opciones', role: 'listbox', 'aria-label': 'Buscar en' });
      const elegirValor = valor => {
        g.columna = valor;
        ponerTexto(columna.querySelector('.texto'), etiquetaColumna());
        cerrarPopoverFiltro();
        if (g.filtro) { g.desde = 0; cargar(); }
        buscar.focus();
      };
      const pintarOpciones = () => {
        limpiar(opciones);
        const q = filtroTexto.value.trim().toLowerCase();
        for (const [valor, texto] of [['', 'Todas las columnas'], ...vista.orden.map(c => [c, c])]) {
          if (q && valor && !texto.toLowerCase().includes(q)) continue;
          const elegida = (g.columna || '') === valor;
          opciones.appendChild(el('button', { type: 'button', role: 'option', class: 'opcion-lista' + (elegida ? ' elegida' : ''), 'aria-selected': String(elegida), onclick: () => elegirValor(valor) },
            el('span', null, texto), elegida ? icono('i-check') : null));
        }
      };
      filtroTexto.addEventListener('input', pintarOpciones);
      filtroTexto.addEventListener('keydown', ev => { if (ev.key === 'Enter') { const b = opciones.querySelector('.opcion-lista:not(.elegida)') || opciones.querySelector('.opcion-lista'); if (b) b.click(); } });
      const { p, reubicar } = abrirPopoverFiltro(columna, [el('div', { class: 'pf-titulo' }, icono('i-buscar'), el('b', null, 'Buscar en')), muchas ? filtroTexto : null, opciones], '__columna', 'Buscar en una columna');
      p.classList.add('popover-columna');
      pintarOpciones();
      reubicar();
      setTimeout(() => (muchas ? filtroTexto : (opciones.querySelector('.elegida') || opciones.firstChild)).focus(), 0);
    };
    const filtros = el('div', { class: 'segmentado', role: 'group', 'aria-label': 'Filtrar por revisión' });
    for (const [valor, texto] of ESTADOS_GRILLA) {
      if (valor === 'revisar' && !info.revisar) continue;
      filtros.appendChild(el('button', { type: 'button', 'data-valor': valor, class: g.estado === valor ? 'activa' : '', title: valor === 'revisar' ? `Las filas que no dan ${info.revisar.salvo.join(' ni ')}` : null,
        onclick: () => { g.estado = valor; g.desde = 0; g.seleccion.clear(); cargar(); } }, texto));
    }
    const cantidad = el('select', { class: 'selector', 'aria-label': 'Filas por página', onchange: ev => { g.cantidad = parseInt(ev.target.value, 10); g.desde = 0; cargar(); } }, [100, 250, 500].map(c => el('option', { value: String(c), text: String(c), selected: g.cantidad === c })));
    const exportarVista = async () => {
      const q = consultaGrilla(g);
      q.set('tabla', info.tabla);
      q.set('columnas', JSON.stringify(vista.visibles));
      try {
        await descargar(`/api/ejecuciones/${encodeURIComponent(e.id)}/exportar-vista?${q}`, `Excel de la vista de ${info.titulo}`, pagina && pagina.total > 20000 ? `${n(pagina.total)} filas: puede tardar unos segundos.` : `${n(pagina ? pagina.total : 0)} filas.`);
      } catch (err) { avisarError(err); }
    };
    cont.appendChild(el('div', { class: 'barra-grilla' }, el('div', { class: 'buscador' }, icono('i-buscar'), buscar, columna), revisable ? filtros : null,
      el('div', { class: 'acciones-grilla' },
        btn('Columnas', () => configurarColumnas(w, info, () => { vista = vistaColumnas(w, info); pintarTabla(); }), 'chico', { icono: 'i-columnas', title: 'Elegir qué columnas ver y en qué orden' }),
        btn('Exportar', exportarVista, 'chico', { icono: 'i-bajar', title: 'Exportar lo que ves: un Excel con todas las filas de este filtro (no sólo esta página), con las columnas a la vista' }))));
    const activos = el('div', { class: 'filtros-activos vacio', 'aria-live': 'polite' });
    const acciones = el('div', { class: 'barra-seleccion vacia' });
    const marco = el('div', { class: 'marco-grilla' });
    const pie = el('div', { class: 'paginado' });
    cont.append(activos, acciones, marco, pie);
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
      if (!cuantas) { acciones.append(icono('i-info'), el('span', null, 'Hacé clic en una o más filas para marcarlas como revisadas u omitidas, o para anotarles una observación. Doble clic en la observación edita una sola fila.' + (conOrigen ? ' El botón verde baja la fila del archivo original en Excel.' : ''))); return; }
      const filas = [...g.seleccion];
      const obs = el('input', { type: 'text', class: 'entrada-texto', placeholder: 'Observación (opcional)…', 'aria-label': 'Observación' });
      acciones.append(el('span', { class: 'cuenta-sel' }, cuantas === 1 ? '1 fila' : `${n(cuantas)} filas`),
        btn('Revisada', () => marcar(filas, 'revisada', obs.value || null), 'chico', { icono: 'i-check' }),
        btn('Omitir', () => marcar(filas, 'omitida', obs.value || null), 'chico', { icono: 'i-ojo-tachado' }),
        btn('Pendiente', () => marcar(filas, 'pendiente', obs.value || null), 'chico fantasma', { icono: 'i-deshacer' }),
        obs, btn('Guardar observación', () => marcar(filas, null, obs.value), 'chico primario', { icono: 'i-mensaje' }),
        btn('', () => { g.seleccion.clear(); pintarAcciones(); pintarTabla(); }, 'fantasma icono chico', { icono: 'i-x', aria: 'Deseleccionar', title: 'Deseleccionar' }));
    };
    // ---- filtro de encabezado (como en Excel): lista de valores en texto, condiciones en importes
    const hayFiltros = () => Object.keys(g.filtros).length + Object.keys(g.condiciones).length > 0;
    const recargarFiltrado = () => { g.desde = 0; g.seleccion.clear(); cerrarPopoverFiltro(); cargar(); };
    const quitarFiltro = c => { delete g.filtros[c]; delete g.condiciones[c]; recargarFiltrado(); };
    const describirFiltro = c => {
      const f = g.filtros[c];
      if (f) {
        if (Array.isArray(f)) return f.length === 1 ? `${c}: ${f[0] || '(vacías)'}` : `${c}: ${n(f.length)} valores`;
        return f.excluir.length === 1 ? `${c}: todos menos ${f.excluir[0] || '(vacías)'}` : `${c}: todos menos ${n(f.excluir.length)} valores`;
      }
      const k = g.condiciones[c];
      return { distinto_cero: `${c} distinto de cero`, igual: `${c} igual a ${importeLegible(k.a)}`, mayor: `${c} mayor que ${importeLegible(k.a)}`,
        menor: `${c} menor que ${importeLegible(k.a)}`, entre: `${c} entre ${importeLegible(Math.min(k.a, k.b))} y ${importeLegible(Math.max(k.a, k.b))}` }[k.op] || c;
    };
    const pintarActivos = () => {
      limpiar(activos);
      const cols = [...new Set([...Object.keys(g.filtros), ...Object.keys(g.condiciones)])];
      activos.classList.toggle('vacio', !cols.length);
      if (!cols.length) return;
      activos.append(...[el('span', { class: 'muted' }, 'Filtrado por:'),
        ...cols.map(c => el('span', { class: 'chip-filtro' }, icono('i-filtro'), el('span', null, describirFiltro(c)),
          el('button', { type: 'button', 'aria-label': 'Quitar el filtro de ' + c, title: 'Quitar este filtro', onclick: () => quitarFiltro(c) }, icono('i-x')))),
        cols.length > 1 ? btn('Quitar todos', () => { g.filtros = {}; g.condiciones = {}; recargarFiltrado(); }, 'fantasma chico', { icono: 'i-x' }) : null].filter(Boolean));
    };
    const filtroDeNumero = (c, cuerpo, pie) => {
      const actual = g.condiciones[c] || { op: 'distinto_cero' };
      const mostrar = v => v == null ? '' : String(v).replace('.', ',');
      const sel = el('select', { class: 'selector', 'aria-label': 'Condición' }, OPERACIONES_NUMERO.map(([v, t]) => el('option', { value: v, text: t, selected: actual.op === v })));
      const a = el('input', { type: 'text', class: 'entrada-texto', inputmode: 'decimal', placeholder: 'Importe', value: mostrar(actual.a), 'aria-label': 'Importe' });
      const y = el('span', { class: 'muted' }, 'y');
      const b = el('input', { type: 'text', class: 'entrada-texto', inputmode: 'decimal', placeholder: 'Importe', value: mostrar(actual.b), 'aria-label': 'Segundo importe' });
      const refrescar = () => { const op = sel.value; a.hidden = op === 'distinto_cero'; y.hidden = b.hidden = op !== 'entre'; };
      sel.addEventListener('change', () => { refrescar(); if (!a.hidden) a.focus(); });
      const aplicar = () => {
        const cond = { op: sel.value };
        if (cond.op !== 'distinto_cero') { cond.a = leerImporte(a.value); if (cond.a === null) { a.focus(); aviso('Escribí un importe válido, por ejemplo -1.500,50.', 'atencion'); return; } }
        if (cond.op === 'entre') { cond.b = leerImporte(b.value); if (cond.b === null) { b.focus(); aviso('Escribí el segundo importe.', 'atencion'); return; } }
        delete g.filtros[c];
        g.condiciones[c] = cond;
        recargarFiltrado();
      };
      for (const x of [a, b]) x.addEventListener('keydown', ev => { if (ev.key === 'Enter') aplicar(); });
      cuerpo.append(sel, el('div', { class: 'pf-importes' }, a, y, b), el('p', { class: 'muted pf-ayuda' }, 'Las celdas vacías no entran en ninguna condición.'));
      refrescar();
      pie.append(btn('Quitar filtro', () => quitarFiltro(c), 'fantasma chico', { icono: 'i-x', disabled: !g.condiciones[c] }), btn('Aplicar', aplicar, 'primario chico', { icono: 'i-check' }));
      setTimeout(() => (a.hidden ? sel : a).focus(), 0);
    };
    const filtroDeValores = async (c, cuerpo, pie, reubicar) => {
      const actual = g.filtros[c];
      const esFecha = pagina.tipos[pagina.columnas.indexOf(c)] === 'fecha';
      const marcadoAntes = v => Array.isArray(actual) ? actual.includes(v) : actual && actual.excluir ? !actual.excluir.includes(v) : true;
      const buscar = el('input', { type: 'search', class: 'entrada-texto', placeholder: 'Buscar un valor…', 'aria-label': 'Buscar un valor' });
      const todas = el('input', { type: 'checkbox', 'aria-label': 'Seleccionar todo' });
      const lista = el('div', { class: 'pf-lista', role: 'group', 'aria-label': 'Valores de ' + c });
      const nota = el('p', { class: 'muted pf-ayuda' });
      let valores = [];
      let completo = true;
      let marcados = new Set();
      const sincronizar = () => {
        todas.checked = valores.length > 0 && valores.every(x => marcados.has(x.valor));
        todas.indeterminate = !todas.checked && valores.some(x => marcados.has(x.valor));
      };
      const pintarLista = () => {
        limpiar(lista);
        for (const x of valores) {
          lista.appendChild(el('label', { class: 'casilla' }, el('input', { type: 'checkbox', checked: marcados.has(x.valor), onchange: ev => { if (ev.target.checked) marcados.add(x.valor); else marcados.delete(x.valor); sincronizar(); } }),
            el('span', { class: 'pf-valor', title: x.valor }, x.valor === '' ? '(vacías)' : esFecha ? fechaCorta(x.valor) : x.valor), el('span', { class: 'muted pf-cantidad' }, n(x.cantidad))));
        }
        if (!valores.length) lista.appendChild(el('p', { class: 'muted pf-ayuda', style: 'padding:6px 0' }, 'Ningún valor coincide.'));
        nota.textContent = completo ? '' : `Se muestran los primeros ${n(valores.length)} valores: escribí para buscar el que necesitás.`;
        sincronizar();
      };
      const cargarValores = async () => {
        const q = consultaGrilla(g, c);
        q.set('valoresDe', c);
        q.set('ordenValores', 'valor');
        q.set('buscar', buscar.value);
        try {
          const d = await api('GET', `/api/ejecuciones/${encodeURIComponent(e.id)}/tablas/${w.tabla}/distintos?${q}`);
          valores = d.valores;
          completo = d.completo;
          marcados = new Set(valores.filter(x => marcadoAntes(x.valor)).map(x => x.valor));
          pintarLista();
          reubicar();
        } catch (err) { avisarError(err); }
      };
      todas.addEventListener('change', () => { for (const x of valores) { if (todas.checked) marcados.add(x.valor); else marcados.delete(x.valor); } pintarLista(); });
      let espera = null;
      buscar.addEventListener('input', () => { clearTimeout(espera); espera = setTimeout(cargarValores, 300); });
      const aplicar = () => {
        const vistos = valores.map(x => x.valor);
        const elegidos = vistos.filter(v => marcados.has(v));
        const buscando = !!buscar.value.trim();
        let nuevo = null;
        // Con la lista completa (o una búsqueda) quedan los marcados; si la lista vino cortada, se excluyen los desmarcados.
        if (buscando) nuevo = elegidos;
        else if (completo) {
          // Va la lista más corta: los tildados, o los destildados como exclusión (con miles de valores tildados, la
          // dirección del pedido quedaba tan larga que se rechazaba).
          const excluidos = vistos.filter(v => !marcados.has(v));
          nuevo = !excluidos.length ? null : excluidos.length < elegidos.length ? { excluir: excluidos } : elegidos;
        }
        else { const excluir = vistos.filter(v => !marcados.has(v)); nuevo = excluir.length ? { excluir } : null; }
        if (Array.isArray(nuevo) && !nuevo.length) { aviso('Marcá al menos un valor.', 'atencion'); return; }
        delete g.condiciones[c];
        if (nuevo) g.filtros[c] = nuevo; else delete g.filtros[c];
        recargarFiltrado();
      };
      buscar.addEventListener('keydown', ev => { if (ev.key === 'Enter') { ev.preventDefault(); clearTimeout(espera); aplicar(); } });
      cuerpo.append(buscar, el('label', { class: 'casilla pf-todas' }, todas, el('span', null, 'Seleccionar todo')), lista, nota);
      pie.append(btn('Quitar filtro', () => quitarFiltro(c), 'fantasma chico', { icono: 'i-x', disabled: !g.filtros[c] }), btn('Aplicar', aplicar, 'primario chico', { icono: 'i-check' }));
      buscar.focus();
      await cargarValores();
    };
    const abrirFiltro = async (c, ancla) => {
      if (popoverFiltro && popoverFiltro.dataset.columna === c) { cerrarPopoverFiltro(); return; }
      const num = pagina.tipos[pagina.columnas.indexOf(c)] === 'numero';
      const fecha = pagina.tipos[pagina.columnas.indexOf(c)] === 'fecha';
      const ordenar = desc => { g.orden = c; g.desc = desc; g.desde = 0; cerrarPopoverFiltro(); cargar(); };
      const cuerpo = el('div', { class: 'pf-cuerpo' });
      const pieFiltro = el('div', { class: 'pf-pie' });
      const { reubicar } = abrirPopoverFiltro(ancla, [
        el('div', { class: 'pf-titulo' }, icono('i-filtro'), el('b', null, c)),
        el('div', { class: 'pf-orden' }, btn(num ? 'Menor a mayor' : fecha ? 'Más antigua primero' : 'De la A a la Z', () => ordenar(false), 'fantasma chico', { icono: 'i-arriba' }),
          btn(num ? 'Mayor a menor' : fecha ? 'Más reciente primero' : 'De la Z a la A', () => ordenar(true), 'fantasma chico', { icono: 'i-abajo' })),
        cuerpo, pieFiltro], c);
      if (num) { filtroDeNumero(c, cuerpo, pieFiltro); reubicar(); } else await filtroDeValores(c, cuerpo, pieFiltro, reubicar);
    };
    const moverColumna = async (origen, destino) => {
      if (!origen || origen === destino || !vista.orden.includes(origen) || !vista.orden.includes(destino)) return;
      const orden = [...vista.orden];
      orden.splice(orden.indexOf(origen), 1);
      orden.splice(vista.orden.indexOf(destino), 0, origen);
      try { await guardarVista(w, info, { orden, ocultas: vista.ocultas }); vista = vistaColumnas(w, info); pintarTabla(); } catch (err) { avisarError(err); }
    };
    const pintarTabla = (cambiadas = new Set(), arriba = false) => {
      const desplazado = [marco.scrollTop, marco.scrollLeft];
      limpiar(marco);
      if (!pagina) return;
      const indices = vista.visibles.map(c => pagina.columnas.indexOf(c)).filter(i => i >= 0);
      const obsDeDatos = pagina.columnas.includes('Observaciones');
      const tabla = el('table', { class: 'grilla' });
      const todas = el('input', { type: 'checkbox', 'aria-label': 'Marcar todas las filas de la página', checked: pagina.filas.length > 0 && pagina.filas.every(f => g.seleccion.has(f._fila)),
        onchange: ev => { for (const f of pagina.filas) { if (ev.target.checked) g.seleccion.add(f._fila); else g.seleccion.delete(f._fila); } pintarAcciones(); pintarTabla(); } });
      const th = c => {
        const activa = g.orden === c;
        const num = pagina.tipos[pagina.columnas.indexOf(c)] === 'numero';
        const filtrada = !!(g.filtros[c] || g.condiciones[c]);
        const celda = el('th', { class: (num ? 'num' : '') + (filtrada ? ' filtrada' : ''), draggable: 'true', 'aria-sort': activa ? (g.desc ? 'descending' : 'ascending') : null },
          el('div', { class: 'th-contenido' },
            el('button', { type: 'button', title: `Ordenar por ${c}. Arrastrá el encabezado para mover la columna.`, onclick: () => { if (activa && !g.desc) g.desc = true; else if (activa && g.desc) { g.orden = null; g.desc = false; } else { g.orden = c; g.desc = false; } g.desde = 0; cargar(); } },
              c, activa ? (() => { const ic = icono('i-abajo'); if (!g.desc) ic.style.transform = 'rotate(180deg)'; return ic; })() : null),
            el('button', { type: 'button', class: 'boton-filtro' + (filtrada ? ' activo' : ''), 'aria-label': `Filtrar ${c}`, 'aria-haspopup': 'dialog',
              title: filtrada ? `Filtro aplicado: ${describirFiltro(c)}` : 'Filtrar como en Excel', onclick: ev => { ev.stopPropagation(); abrirFiltro(c, celda); } }, icono('i-filtro'))));
        celda.addEventListener('dragstart', ev => { ev.dataTransfer.setData('text/plain', c); ev.dataTransfer.effectAllowed = 'move'; celda.classList.add('arrastrando'); });
        celda.addEventListener('dragend', () => celda.classList.remove('arrastrando'));
        celda.addEventListener('dragover', ev => { ev.preventDefault(); celda.classList.add('destino'); });
        celda.addEventListener('dragleave', () => celda.classList.remove('destino'));
        celda.addEventListener('drop', ev => { ev.preventDefault(); celda.classList.remove('destino'); moverColumna(ev.dataTransfer.getData('text/plain'), c); });
        return celda;
      };
      tabla.appendChild(el('thead', null, el('tr', null,
        revisable ? el('th', { class: 'sel' }, todas) : null,
        conOrigen ? el('th', { class: 'col-acciones', title: 'Excel de origen de la fila' }, 'Origen') : null,
        revisable ? el('th', null, el('button', { type: 'button', onclick: () => { g.orden = g.orden === '_estado' ? null : '_estado'; g.desde = 0; cargar(); } }, 'Revisión')) : null,
        indices.map(i => th(pagina.columnas[i])),
        revisable ? el('th', null, obsDeDatos ? 'Observación de la revisión' : 'Observaciones') : null)));
      const cuerpo = el('tbody');
      for (const f of pagina.filas) {
        const tr = el('tr', { class: (g.seleccion.has(f._fila) ? 'seleccionada ' : '') + f._estado + (cambiadas.has(f._fila) ? ' cambio' : '') });
        const casilla = el('input', { type: 'checkbox', checked: g.seleccion.has(f._fila), 'aria-label': 'Marcar fila', onchange: ev => { if (ev.target.checked) g.seleccion.add(f._fila); else g.seleccion.delete(f._fila); tr.classList.toggle('seleccionada', ev.target.checked); pintarAcciones(); } });
        if (revisable) tr.appendChild(el('td', { class: 'sel' }, casilla));
        if (conOrigen) tr.appendChild(el('td', { class: 'col-acciones' }, btn('', () => excelDeOrigen(e, info.tabla, f._fila, f.valores[['Comprobante', 'NumeroFactura', 'NumeroComprobanteImputacion'].map(c => pagina.columnas.indexOf(c)).find(i => i >= 0)]), 'fantasma icono chico boton-origen', { icono: 'i-planilla', aria: 'Excel de origen de esta fila', title: 'Bajar en Excel las filas del archivo original que forman esta fila' })));
        const origen = f._origen && f._origen !== 'manual' && f._estado !== 'pendiente' ? { version: 'de la versión anterior', cierre: 'del cierre anterior', importado: 'importada' }[f._origen] : null;
        if (revisable) tr.appendChild(el('td', { class: 'revision', title: origen ? 'Marca ' + origen : null },
          f._estado === 'revisada' ? el('span', { class: 'chip ok' }, icono('i-check'), 'Revisada') : f._estado === 'omitida' ? el('span', { class: 'chip' }, icono('i-ojo-tachado'), 'Omitida')
            : f._req === false ? el('span', { class: 'chip tenue', title: `No hace falta revisarla: ${textoRegla(info.revisar)}` }, 'No requiere') : el('span', { class: 'chip borde' }, 'Pendiente')));
        for (const i of indices) {
          const v = f.valores[i];
          const nombre = pagina.columnas[i];
          const num = pagina.tipos[i] === 'numero';
          const contenido = (nombre === 'Resultado' || nombre === 'Estado') && v ? celdaResultado(v) : num ? numeroLegible(v) : pagina.tipos[i] === 'fecha' ? fechaCorta(v) : v;
          tr.appendChild(el('td', { class: (num ? 'num' : '') + (f._marcas.includes(nombre) ? ' resaltada' : ''), title: v && v.length > 36 ? v : null }, contenido));
        }
        if (!revisable) { tr.style.cursor = 'default'; cuerpo.appendChild(tr); continue; }
        const celdaObs = el('td', { class: 'obs', title: f._obs ? f._obs : 'Doble clic para escribir una observación' }, f._obs || '');
        tr.appendChild(celdaObs);
        tr.addEventListener('click', ev => { if (ev.target.closest('input,button')) return; casilla.checked = !casilla.checked; casilla.dispatchEvent(new Event('change')); });
        celdaObs.addEventListener('dblclick', async ev => {
          ev.stopPropagation();
          const t = await pedirTexto('Observación', 'Lo que quieras anotar sobre esta fila.', f._obs || '', true);
          if (t === null) return;
          await marcar([f._fila], null, t);
        });
        cuerpo.appendChild(tr);
      }
      const columnasTotales = indices.length + (revisable ? 3 : 0) + (conOrigen ? 1 : 0);
      if (!pagina.filas.length) cuerpo.appendChild(el('tr', null, el('td', { colspan: String(columnasTotales), class: 'vacia' },
        g.filtro || hayFiltros() || (g.estado && g.estado !== 'revisar') ? 'Ninguna fila coincide con el filtro.' : g.estado === 'revisar' ? `No hay filas para revisar: todas dan ${info.revisar.salvo.join(' o ')}.` : 'Esta tabla está vacía: no hay nada para revisar.')));
      tabla.appendChild(cuerpo);
      marco.appendChild(tabla);
      marco.scrollTop = arriba ? 0 : desplazado[0];
      marco.scrollLeft = desplazado[1];
      limpiar(pie);
      const desde = pagina.total ? g.desde + 1 : 0;
      const hasta = Math.min(g.desde + g.cantidad, pagina.total);
      const ocultas = vista.ocultas.size;
      pie.append(el('div', { class: 'pie-izq' }, el('span', null, `Filas ${n(desde)} a ${n(hasta)} de ${n(pagina.total)}` + (ocultas ? ` · ${ocultas === 1 ? 'una columna oculta' : n(ocultas) + ' columnas ocultas'}` : '')),
          el('label', { class: 'por-pagina' }, cantidad, el('span', null, 'por página'))),
        el('div', { class: 'botones' }, btn('Anterior', () => { g.desde = Math.max(0, g.desde - g.cantidad); cargar(); }, 'chico', { icono: 'i-izq', disabled: g.desde === 0 }), btn('Siguiente', () => { g.desde += g.cantidad; cargar(); }, 'chico', { icono: 'i-der', disabled: hasta >= pagina.total })));
    };
    const cargar = async (cambiadas) => {
      const q = consultaGrilla(g);
      q.set('desde', g.desde);
      q.set('cantidad', g.cantidad);
      const espera = setTimeout(() => marco.classList.add('cargando'), 180);
      try { pagina = await api('GET', `/api/ejecuciones/${encodeURIComponent(e.id)}/tablas/${w.tabla}?${q}`); } catch (err) { avisarError(err); return; }
      finally { clearTimeout(espera); marco.classList.remove('cargando'); }
      for (const b of filtros.children) b.classList.toggle('activa', b.dataset.valor === g.estado);
      pintarActivos();
      pintarAcciones();
      const tras = cambiadas instanceof Set;
      pintarTabla(tras ? cambiadas : new Set(), !tras);
    };
    await cargar();
  }

  // paso 5
  // Armado del Excel en un renglón: qué filas, qué estado de revisión y qué columnas. Elegir una opción sólo cambia
  // su marca y la cuenta de filas (no se redibuja el formulario: así no parpadea).
  async function pasoExportar(cont, w) {
    const { e, reporte, cierre } = w;
    const base = `/api/ejecuciones/${encodeURIComponent(e.id)}`;
    const datos = await api('GET', `${base}/tablas`);
    w.tablas = datos.tablas;
    const revisables = datos.tablas.filter(t => t.revisable !== false);
    const elegibles = [...revisables, ...datos.tablas.filter(t => t.revisable === false)];
    const op = { tabla: (elegibles.find(t => t.principal) || elegibles[0] || {}).tabla, filas: null, valores: null, estados: new Set(['pendiente', 'revisada', 'omitida']), conObs: false, columnas: 'vista', resumen: true };
    let actual = null;
    let total = 0;
    let turno = 0;
    const formulario = el('div', { class: 'armado-excel' });
    const cuenta = el('div', { class: 'cuenta-exportar', role: 'status' }, icono('i-planilla'), el('span', null, 'Contando filas…'));
    const consulta = () => {
      const { info, colValores } = actual;
      const q = new URLSearchParams({ tabla: info.tabla });
      if (op.filas === 'revisar') q.set('requiere', '1');
      if (op.filas === 'valores' && colValores && op.valores) q.set('filtros', JSON.stringify({ [colValores]: [...op.valores] }));
      if (info.revisable !== false && op.estados.size < 3) q.set('estados', [...op.estados].join(','));
      if (op.conObs) q.set('conObs', '1');
      return q;
    };
    const descargarElegido = async () => {
      const { info, vista, informativas } = actual;
      const q = consulta();
      q.set('columnas', JSON.stringify(op.columnas === 'vista' ? vista.visibles : info.columnas));
      if (op.resumen && informativas.length) q.set('resumen', '1');
      try { await descargar(`${base}/exportar-vista?${q}`, `Excel de ${info.titulo}`, total > 20000 ? `${n(total)} filas: puede tardar unos segundos.` : `${n(total)} filas.`); } catch (err) { avisarError(err); }
    };
    const botonDescargar = btn('Descargar Excel', descargarElegido, 'primario', { icono: 'i-bajar' });
    const ponerCuenta = (texto, nodoNumero) => {
      cuenta.classList.remove('contando');
      limpiar(cuenta).append(icono('i-planilla'), el('span', null, nodoNumero || '', texto));
    };
    const contar = async () => {
      const mio = ++turno;
      if (actual.info.revisable !== false && !op.estados.size) { total = 0; ponerCuenta('Elegí al menos un estado de revisión.'); botonDescargar.disabled = true; return; }
      if (op.filas === 'valores' && op.valores && !op.valores.size) { total = 0; ponerCuenta('Elegí al menos un valor.'); botonDescargar.disabled = true; return; }
      cuenta.classList.add('contando');
      const q = consulta();
      q.set('cantidad', '1');
      try {
        const r = await api('GET', `${base}/tablas/${actual.info.tabla}?${q}`, undefined, { silencioso: true });
        if (mio !== turno) return;
        total = r.total;
        if (total) ponerCuenta(total === 1 ? ' va a salir en el Excel.' : ' van a salir en el Excel.', el('b', null, total === 1 ? 'Una fila' : `${n(total)} filas`));
        else ponerCuenta('Ninguna fila cumple lo elegido.');
        botonDescargar.disabled = !total;
      } catch (err) { if (mio === turno) { ponerCuenta(err.message); botonDescargar.disabled = true; } }
    };
    // Una opción de radio con forma de tarjeta (todas de la misma altura; el detalle va en una línea).
    const opcion = (grupo, valor, titulo, detalle, alElegir) => {
      const input = el('input', { type: 'radio', name: 'exp-' + grupo, value: valor, checked: op[grupo] === valor,
        onchange: () => { op[grupo] = valor; for (const l of formulario.querySelectorAll(`.opcion-fila[data-grupo="${grupo}"]`)) l.classList.toggle('elegida', l.dataset.valor === valor); if (alElegir) alElegir(); if (grupo !== 'columnas') contar(); } });
      return el('label', { class: 'opcion-fila' + (op[grupo] === valor ? ' elegida' : ''), 'data-grupo': grupo, 'data-valor': valor, title: detalle },
        input, el('span', { class: 'textos' }, el('b', null, titulo), el('small', null, detalle)));
    };
    const armar = () => {
      const info = datos.tablas.find(t => t.tabla === op.tabla);
      limpiar(formulario);
      if (!info) { formulario.appendChild(el('p', { class: 'muted' }, 'Esta corrida no dejó tablas para exportar.')); botonDescargar.disabled = true; return; }
      const regla = info.revisar;
      const colValores = (regla && regla.columna) || ['Resultado', 'Estado', 'Motivo'].find(c => info.columnas.includes(c)) || null;
      if (op.filas === null || (op.filas === 'revisar' && !regla) || (op.filas === 'valores' && !colValores)) op.filas = regla ? 'revisar' : 'todas';
      const vista = vistaColumnas(w, info);
      const informativas = datos.tablas.filter(t => t.revisable === false && t.archivo && t.archivo === info.archivo && t.tabla !== info.tabla);
      actual = { info, colValores, vista, informativas };
      // valores de la columna de resultado: se piden una sola vez, la primera vez que se elige "Por …"
      const cajaValores = el('div', { class: 'valores-exportar' + (op.filas === 'valores' ? '' : ' oculto') });
      let valoresPedidos = false;
      const mostrarValores = async () => {
        cajaValores.classList.toggle('oculto', op.filas !== 'valores');
        if (op.filas !== 'valores' || valoresPedidos || !colValores) return;
        valoresPedidos = true;
        cajaValores.appendChild(el('p', { class: 'muted cargando-texto' }, el('span', { class: 'girador' }), 'Buscando los valores…'));
        try {
          const d = await api('GET', `${base}/tablas/${info.tabla}/distintos?${new URLSearchParams({ valoresDe: colValores })}`);
          if (!op.valores) op.valores = new Set(d.valores.filter(x => !(regla && regla.salvo.includes(x.valor))).map(x => x.valor));
          limpiar(cajaValores);
          for (const x of d.valores) {
            cajaValores.appendChild(el('label', { class: 'casilla' }, el('input', { type: 'checkbox', checked: op.valores.has(x.valor), onchange: ev => { if (ev.target.checked) op.valores.add(x.valor); else op.valores.delete(x.valor); contar(); } }),
              el('span', { class: 'pf-valor', title: x.valor }, x.valor || '(vacías)'), el('span', { class: 'muted pf-cantidad' }, n(x.cantidad))));
          }
          if (!d.completo) cajaValores.appendChild(el('p', { class: 'muted' }, 'Se muestran los valores más frecuentes.'));
          contar();
        } catch (err) { valoresPedidos = false; limpiar(cajaValores); avisarError(err); }
      };
      const columnaFilas = el('div', { class: 'col-exportar' }, el('h3', null, icono('i-tabla'), 'Qué filas'),
        regla ? opcion('filas', 'revisar', 'Para revisar', `${n(info.aRevisar)} filas: las que no dan ${regla.salvo.join(' ni ')}`, mostrarValores) : null,
        opcion('filas', 'todas', 'Todas', `${n(info.filas)} filas de la tabla`, mostrarValores),
        colValores ? opcion('filas', 'valores', `Por ${colValores}`, 'Marcás los valores que querés', mostrarValores) : null,
        cajaValores);
      const casilla = (activo, texto, alCambiar) => el('label', { class: 'casilla' }, el('input', { type: 'checkbox', checked: activo, onchange: ev => { alCambiar(ev.target.checked); contar(); } }), el('span', null, texto));
      const columnaRevision = info.revisable !== false ? el('div', { class: 'col-exportar' }, el('h3', null, icono('i-check-circulo'), 'Estado de la revisión'),
        el('div', { class: 'casillas-exportar' },
          ...[['pendiente', 'Pendientes'], ['revisada', 'Revisadas'], ['omitida', 'Omitidas']].map(([v, t]) => casilla(op.estados.has(v), t, si => { if (si) op.estados.add(v); else op.estados.delete(v); })),
          casilla(op.conObs, 'Sólo las que tienen observación', si => { op.conObs = si; }))) : null;
      const columnaColumnas = el('div', { class: 'col-exportar' }, el('h3', null, icono('i-columnas'), 'Qué columnas'),
        opcion('columnas', 'vista', 'Las de tu vista', `${n(vista.visibles.length)} columnas, en el orden de Resultados`),
        opcion('columnas', 'todas', 'Todas', `${n(info.columnas.length)} columnas, en el orden del reporte`),
        informativas.length ? el('label', { class: 'casilla', style: 'margin-top:4px' }, el('input', { type: 'checkbox', checked: op.resumen, onchange: ev => { op.resumen = ev.target.checked; } }),
          el('span', null, `Agregar ${informativas.map(t => t.titulo).join(' y ')} como primera hoja`)) : null);
      const selTabla = elegibles.length > 1 ? el('div', { class: 'campo selector-tabla' }, el('label', { for: 'exp-tabla' }, 'Tabla'),
        el('select', { id: 'exp-tabla', class: 'selector', onchange: ev => { op.tabla = ev.target.value; op.filas = null; op.valores = null; armar(); } },
          elegibles.map(t => el('option', { value: t.tabla, text: (t.hoja && t.hoja !== t.titulo ? `${t.titulo} (${t.hoja})` : t.titulo) + ` · ${n(t.filas)} filas`, selected: t.tabla === op.tabla })))) : null;
      formulario.classList.toggle('sin-revision', !columnaRevision);
      formulario.append(...[selTabla, columnaFilas, columnaRevision, columnaColumnas, el('div', { class: 'pie-armado' }, cuenta, botonDescargar)].filter(Boolean));
      mostrarValores();
      contar();
    };
    const libros = [...new Set(datos.tablas.map(t => t.archivo).filter(Boolean))];
    const sinOmitidas = el('input', { type: 'checkbox', id: 'sin-omitidas' });
    const listaLibros = el('div', { class: 'lista-descargas' });
    const pintarLibros = () => {
      limpiar(listaLibros);
      for (const libro of libros) {
        const nombre = libros.length === 1 ? reporte.nombre : libro.replace(/\.(xlsx|csv|txt)$/i, '').replace(/_/g, ' ');
        listaLibros.appendChild(el('button', { type: 'button', class: 'descarga', onclick: async ev => {
          const b = ev.currentTarget;
          b.classList.add('cargando');
          try { await descargar(`${base}/exportar?libro=${encodeURIComponent(libro)}${sinOmitidas.checked ? '&incluirOmitidas=0' : ''}`, `Libro completo de ${nombre}`, 'Todas las solapas y todas las filas.'); }
          catch (err) { avisarError(err); } finally { b.classList.remove('cargando'); }
        } }, el('span', { class: 'icono-archivo' }, icono('i-planilla', 'g')),
          el('span', { class: 'datos' }, el('b', null, nombre), el('small', null, 'Libro completo · ' + datos.tablas.filter(t => t.archivo === libro).map(t => t.hoja || t.titulo).join(', '))), icono('i-bajar')));
      }
    };
    sinOmitidas.addEventListener('change', pintarLibros);
    pintarLibros();
    const final = el('input', { type: 'checkbox', checked: !!e.final, onchange: async ev => {
      try {
        const r = await api('PATCH', base, { final: ev.target.checked });
        w.e = r;
        aviso(r.final ? `Listo: esta versión es el resultado final de ${reporte.nombre}.` : 'Ya no es el resultado final.', r.final ? 'ok' : 'info');
      } catch (err) { avisarError(err); ev.target.checked = !ev.target.checked; }
    } });
    cont.append(...[intro('i-bajar', 'Armá el Excel que necesitás: qué filas, qué estado de revisión y qué columnas. Sale con la columna Revisión y tus observaciones.'),
      el('div', { class: 'tarjeta tarjeta-exportar' }, formulario),
      libros.length ? el('details', { class: 'avanzadas' },
        el('summary', null, icono('i-capas'), el('span', null, 'Libros completos del reporte ', el('span', { class: 'muted' }, '(todas las solapas y todas las filas, con tu revisión)')), icono('i-abajo', 'flecha')),
        el('div', { class: 'contenido' }, el('label', { class: 'casilla', for: 'sin-omitidas', style: 'margin-bottom:8px' }, sinOmitidas, el('span', null, 'Sin las filas omitidas')), listaLibros)) : null,
      el('div', { class: 'pie-paso' },
        el('label', { class: 'interruptor' }, final, el('span', { class: 'riel' }), el('span', null, el('b', null, 'Resultado final'), el('br'), el('span', { class: 'muted' }, `Esta versión es la que vale para ${cierre.herramienta ? 'el registro' : 'el cierre de ' + periodoLargo(cierre.periodo).toLowerCase()}.`))),
        el('div', { class: 'der' }, cierre.herramienta ? null : btn('Exportar el cierre completo', () => exportarCierre(cierre), 'fantasma', { icono: 'i-caja' }),
          btn('Nueva versión', nuevaVersion(w), 'fantasma', { icono: 'i-refrescar' }), enlace(cierre.herramienta ? 'Volver a Facturas' : 'Volver al cierre', cierre.herramienta ? '#/facturas' : '#/cierre/' + encodeURIComponent(cierre.id), 'btn primario', 'i-volver')))].filter(Boolean));
    armar();
  }
  // El cierre completo en un archivo, para compartirlo (con su tarea).
  async function exportarCierre(cierre) {
    try { await descargar(`/api/cierres/${encodeURIComponent(cierre.id)}/exportar`, `Cierre de ${periodoLargo(cierre.periodo)}`, 'Resultados trabajados, resumen y observaciones.'); } catch (err) { avisarError(err); }
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
        el('td', null, el('a', { class: 'celda-reporte', href: '#/ejecucion/' + encodeURIComponent(x.id), style: 'color:inherit;text-decoration:none' }, tileReporte(r), el('b', null, r.nombre), chipVariante(varianteDe(r, x), 'chico'))),
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
    const main = pantallaNueva();
    const periodos = Object.fromEntries(cierres.map(c => [c.id, c.periodo]));
    const filtro = { cierre: partes[1] || '', reporte: partes[2] || '', estado: '', variante: partes[3] || '' };
    const nombresReporte = Object.fromEntries(app.reportes.map(r => [r.codigo, r]));
    const fondos = app.reportes.flatMap(r => r.variantes ? r.variantes.opciones : []);
    main.appendChild(el('div', { class: 'encabezado entrar' }, el('div', null, el('h1', null, 'Historial'), el('div', { class: 'sub' }, 'Todas las corridas, de todos los cierres. Las versiones viejas se pueden borrar desde el menú de cada fila.'))));
    const selCierre = el('select', { class: 'selector', 'aria-label': 'Cierre', onchange: ev => { filtro.cierre = ev.target.value; pintar(); } }, el('option', { value: '', text: 'Todos los cierres' }), cierres.map(c => el('option', { value: c.id, text: periodoLargo(c.periodo), selected: filtro.cierre === c.id })));
    const selReporte = el('select', { class: 'selector', 'aria-label': 'Reporte', onchange: ev => { filtro.reporte = ev.target.value; pintar(); } }, el('option', { value: '', text: 'Todos los reportes' }), app.reportes.map(r => el('option', { value: r.codigo, text: r.nombre, selected: filtro.reporte === r.codigo })));
    const selEstado = el('select', { class: 'selector', 'aria-label': 'Estado', onchange: ev => { filtro.estado = ev.target.value; pintar(); } }, el('option', { value: '', text: 'Cualquier estado' }), Object.entries(ESTADO_TEXTO).map(([v, t]) => el('option', { value: v, text: t })));
    const selFondo = fondos.length ? el('select', { class: 'selector', 'aria-label': 'Fondo de riesgo', onchange: ev => { filtro.variante = ev.target.value; pintar(); } },
      el('option', { value: '', text: 'Cualquier fondo' }), fondos.map(o => el('option', { value: o.valor, text: o.titulo, selected: filtro.variante === o.valor }))) : null;
    main.appendChild(el('div', { class: 'barra-grilla entrar' }, icono('i-filtro'), selCierre, selReporte, selFondo, selEstado));
    const marco = el('div');
    main.appendChild(marco);
    const pintar = () => {
      limpiar(marco);
      const lista = ejecuciones.filter(x => (!filtro.cierre || x.cierreId === filtro.cierre) && (!filtro.reporte || x.reporte === filtro.reporte) && (!filtro.estado || x.estado === filtro.estado)
        && (!filtro.variante || (varianteDe(nombresReporte[x.reporte], x) || {}).valor === filtro.variante));
      if (!lista.length) { marco.appendChild(el('div', { class: 'vacio' }, el('div', { class: 'ilustracion' }, icono('i-historial')), el('h2', null, ejecuciones.length ? 'No hay corridas con ese filtro' : 'Todavía no hay corridas'), el('p', null, 'Cada vez que corras un reporte, la versión va a quedar registrada acá.'))); return; }
      marco.appendChild(tablaEjecuciones(lista, { periodos, alBorrar: x => { ejecuciones.splice(ejecuciones.indexOf(x), 1); pintar(); } }));
    };
    pintar();
  }

  // ---------------------------------------------------------------- vista: configuración
  // Configuración en una ventana, como la de PedidosIA: el índice de secciones a la izquierda y una sección a la vista.
  // Cada sección guarda como siempre (el tema al elegirlo, el resto con su botón): cerrar no pierde nada.
  async function abrirConfiguracion(inicial = 'apariencia') {
    const [conf, app] = await Promise.all([api('GET', '/api/configuracion'), api('GET', '/api/estado')]);
    estado.app = app;
    estado.conf = conf;
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
    const cerrarVentana = () => { const d = $('#modal'); if (d.open) d.close(); };
    const secciones = [
      ['apariencia', 'i-sol', 'Apariencia', 'El tema claro es el predeterminado.', el('div', { class: 'campo' }, el('div', { class: 'rotulo' }, 'Tema'), temaSeg)],
      ['archivos', 'i-archivo', 'Archivos', 'Los reportes históricos suelen pesar entre 50 y 100 MB.', el('div', { class: 'campo' }, el('label', { for: 'limite' }, 'Tamaño máximo de cada archivo (MB)'), limite),
        btn('Guardar', async () => { try { await api('PATCH', '/api/configuracion', { limiteMB: parseInt(limite.value, 10) }); aviso('Guardado.', 'ok'); } catch (err) { avisarError(err); } }, 'chico', { icono: 'i-check' })],
      ['valores', 'i-ajustes', 'Valores por defecto', 'Lo que guardes acá aparece ya cargado en el paso Opciones de cada reporte. En cada corrida se puede cambiar igual.',
        el('div', { class: 'campo', style: 'max-width:340px' }, el('div', { class: 'rotulo' }, 'Reporte'), selReporte), formDefaults],
      ['datos', 'i-carpeta', 'Dónde están los datos', 'Los cierres, los archivos agregados, los resultados y las revisiones se guardan en esta carpeta de tu PC. No la compartas ni la pongas en OneDrive: para mandar un cierre usá "Exportar el cierre".',
        el('p', null, el('code', null, conf.carpetaDatos)),
        btn('Liberar espacio', async () => {
          if (!await confirmar('¿Liberar espacio?', 'Se borran los Excel agregados que ninguna versión final usa. Los resultados y las revisiones se conservan.', 'Liberar espacio')) return;
          try { await tareas.correr({ clave: 'limpieza', titulo: 'Limpiando archivos sin usar' }, async () => { const r = await api('POST', '/api/limpieza', {}); return `Se liberaron ${r.liberadosMB} MB.`; }); } catch (err) { avisarError(err); }
        }, '', { icono: 'i-basura' })],
      ['acceso', 'i-pc', 'Acceso directo', 'La herramienta crea sola el acceso directo "Reportes de cierre" la primera vez que se abre. Si lo borraste, volvé a crearlo acá.',
        btn('Crear el acceso directo en el Escritorio', async () => { try { await api('POST', '/api/acceso-directo', {}); aviso('Listo: en el Escritorio está el acceso directo "Reportes de cierre".', 'ok'); } catch (err) { avisarError(err); } }, '', { icono: 'i-pc' })],
      ['herramienta', 'i-info', 'La herramienta', `Versión ${app.version}. Si algo falla o se cierra sola, tocá "Reportar un problema": baja un archivo para mandarle a quien te da soporte.`, el('div', { class: 'acciones-fila' },
        btn('Ver la guía de inicio', () => { cerrarVentana(); bienvenida(); }, '', { icono: 'i-chispa' }),
        btn('Reiniciar la herramienta', () => { cerrarVentana(); reiniciarHerramienta(); }, '', { icono: 'i-refrescar' }),
        btn('Reportar un problema', () => descargar('/api/registro', 'Reporte del problema', 'Juntando el registro de la herramienta…').catch(avisarError), '', {
          icono: 'i-mensaje',
          title: 'Baja un archivo con lo que pasó en la herramienta (cuándo se abrió y se cerró, y los errores). Mandáselo a quien te da soporte junto con lo que estabas haciendo.' }),
        btn('Cerrar la herramienta', () => { cerrarVentana(); cerrarHerramienta(); }, 'peligro', { icono: 'i-apagar' }))],
    ];
    const indice = el('nav', { class: 'config-indice', 'aria-label': 'Secciones de la configuración' });
    const texto = el('div', { class: 'config-texto' });
    const mostrar = id => {
      for (const b of indice.children) { const si = b.dataset.seccion === id; b.classList.toggle('activa', si); b.setAttribute('aria-current', si ? 'true' : 'false'); }
      for (const s of texto.children) s.classList.toggle('activa', s.dataset.seccion === id);
      texto.scrollTop = 0;
    };
    for (const [id, ic, titulo, bajada, ...contenido] of secciones) {
      indice.appendChild(el('button', { type: 'button', 'data-seccion': id, onclick: () => mostrar(id) }, icono(ic), el('span', null, titulo)));
      texto.appendChild(el('section', { 'data-seccion': id }, el('h3', null, icono(ic), titulo), el('p', { class: 'muted bajada' }, bajada), contenido));
    }
    abrirModal({ titulo: 'Configuración', iconoNombre: 'i-ajustes', ancho: true, cuerpo: el('div', { class: 'config-cuerpo' }, indice, texto),
      pie: [btn('Listo', cerrarVentana, 'primario', { icono: 'i-check' })] });
    mostrar(secciones.some(s => s[0] === inicial) ? inicial : 'apariencia');
    await pintarDefaults();
  }
  // Reinicia la herramienta: vuelve sola con el mismo acceso y la pantalla se recarga cuando la nueva responde.
  async function reiniciarHerramienta() {
    if (!await confirmar('¿Reiniciar la herramienta?', 'Se cierra y se vuelve a abrir sola en unos segundos, con lo último que se haya instalado. Lo que tenés guardado no se pierde.', 'Reiniciar', 'pregunta')) return;
    let anterior = null;
    try { anterior = (await api('GET', '/api/estado', undefined, { silencioso: true })).instancia; estado.saliendo = true; await api('POST', '/api/reiniciar', {}); } catch (err) { avisarError(err); return; }
    if (estado.fuente) { estado.fuente.close(); estado.fuente = null; }
    const texto = el('span', null, 'Esperando que vuelva a abrir…');
    abrirModal({ titulo: 'Reiniciando la herramienta', iconoNombre: 'i-refrescar', cuerpo: el('p', { class: 'cargando-texto' }, el('span', { class: 'girador' }), texto) });
    const inicio = Date.now();
    while (Date.now() - inicio < 45000) {
      await new Promise(r => setTimeout(r, 700));
      try {
        const r = await fetch('/api/estado', { credentials: 'same-origin', cache: 'no-store' });
        if (r.ok && (await r.json()).instancia !== anterior) { location.reload(); return; }
      } catch (err) { /* todavía no volvió */ }
    }
    estado.saliendo = false;
    texto.textContent = 'No volvió a abrirse sola. Abrila desde el acceso directo "Reportes de cierre".';
  }
  async function cerrarHerramienta() {
    if (!await confirmar('¿Cerrar la herramienta?', 'Para volver a abrirla, usá el acceso directo "Reportes de cierre". Si cerrás la pestaña sin cerrarla, se apaga sola tres horas después.', 'Cerrar', 'aviso')) return;
    try {
      estado.saliendo = true;
      await api('POST', '/api/cerrar', {});
      if (estado.fuente) { estado.fuente.close(); estado.fuente = null; }
      for (const d of document.querySelectorAll('dialog[open]')) d.close();
      tareas.abrir(false);
      $('#banda-version').classList.add('oculto');
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
      { icono: 'i-ajustes', texto: 'Configuración', onclick: () => abrirConfiguracion().catch(avisarError) },
      'sep',
      { icono: 'i-refrescar', texto: 'Reiniciar la herramienta', detalle: 'Se cierra y vuelve a abrir sola', onclick: reiniciarHerramienta },
      { icono: 'i-apagar', texto: 'Cerrar la herramienta', peligro: true, onclick: cerrarHerramienta },
    ]);
  });
  $('#btn-tareas').addEventListener('click', ev => { ev.stopPropagation(); tareas.abrir(); });
  $('#panel-tareas .tareas-limpiar').addEventListener('click', () => tareas.sacarTerminadas());
  $('#btn-reiniciar').addEventListener('click', () => reiniciarHerramienta());
  document.addEventListener('visibilitychange', () => { if (!document.hidden && estado.fuente) revisarVersion(); });
  window.addEventListener('hashchange', enrutar);
  (async () => {
    try {
      estado.conf = await api('GET', '/api/configuracion');
      aplicarTema(estado.conf.tema || 'claro');
    } catch (err) { /* sigue con lo local */ }
    conectarEventos();
    enrutar();
    const st = await revisarVersion();
    if (st) for (const o of st.origenes || []) tareas.desdeOrigen(o);
    try {
      const desde = Date.now() / 1000 - 12 * 3600;
      for (const tr of await api('GET', '/api/trabajos')) if ((tr.inicio || 0) >= desde) tareas.desdeTrabajo(tr, true);
    } catch (err) { /* el visor arranca vacío */ }
  })();
})();

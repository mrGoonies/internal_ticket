document.addEventListener('DOMContentLoaded', function () {
  var form = document.querySelector('[data-ticket-form]');
  if (!form) return;

  var badge = document.querySelector('[data-stub-badge]');
  var titulo = document.querySelector('[data-stub-title]');
  var tituloInput = form.querySelector('#id_titulo');
  var tipoInputs = form.querySelectorAll('input[name="tipo_solicitud"]');

  function actualizarTipo() {
    var seleccionado = form.querySelector('input[name="tipo_solicitud"]:checked');
    if (!seleccionado || !badge) return;
    var esIncidencia = seleccionado.value === 'INCIDENCIA';
    badge.textContent = esIncidencia ? 'Incidencia' : 'Requerimiento';
    badge.classList.toggle('is-incidencia', esIncidencia);
  }

  function actualizarTitulo() {
    if (!titulo || !tituloInput) return;
    titulo.textContent = tituloInput.value.trim() || 'Tu solicitud aparecera aqui';
  }

  tipoInputs.forEach(function (input) {
    input.addEventListener('change', actualizarTipo);
  });
  if (tituloInput) {
    tituloInput.addEventListener('input', actualizarTitulo);
  }

  var fileInput = form.querySelector('#id_adjuntos');
  var fileHint = document.querySelector('[data-file-hint]');
  if (fileInput && fileHint) {
    fileInput.addEventListener('change', function () {
      var n = fileInput.files.length;
      fileHint.textContent = n
        ? n + (n === 1 ? ' archivo seleccionado' : ' archivos seleccionados')
        : 'Puedes adjuntar capturas de pantalla u otros archivos.';
    });
  }

  actualizarTipo();
  actualizarTitulo();
});

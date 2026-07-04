/* Shared attachment behavior for the notes module (refactoring step 3).
 *
 * ONE copy replaces the ~9 per-template inline scripts. Works by event
 * delegation on document, so it is safe to load on every page (base.html);
 * pages without .att-file inputs simply never trigger it.
 *
 * Behaviors:
 *  - picking a file in an .att-file input uploads it to the note
 *  - hovering a .note-item arms it as the Ctrl+V paste target (Snipping Tool)
 *  - .att-del buttons delete an attachment (with confirm)
 */
(function () {
  function appendThumb(noteId, att) {
    var container = document.getElementById("atts-" + noteId);
    if (!container) return;
    var div = document.createElement("div");
    div.className = "att-thumb";
    div.id = "att-" + att.id;
    var isImg = /\.(png|jpe?g|gif|webp)$/i.test(att.filename);
    div.innerHTML = (isImg
      ? '<a href="/uploads/' + att.filename + '" target="_blank" rel="noopener"><img src="/uploads/' + att.filename + '" alt="' + att.original_name + '"></a>'
      : '<a href="/uploads/' + att.filename + '" target="_blank" rel="noopener" class="att-doclink">&#128196; ' + att.original_name + '</a>') +
      '<span class="att-name">' + att.original_name + '</span>' +
      '<button class="att-del" data-note="' + noteId + '" data-att="' + att.id + '" title="Remove attachment">&#10005;</button>';
    container.appendChild(div);
  }

  function upload(noteId, file, done) {
    var fd = new FormData();
    fd.append("file", file, file.name || ("paste-" + Date.now() + ".png"));
    fetch("/notes/" + noteId + "/attachments/add", { method: "POST", body: fd })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (!data.ok) { alert("Upload failed: " + data.error); return; }
        appendThumb(noteId, data.attachment);
        if (done) done();
      })
      .catch(function () { alert("Upload error — check console."); });
  }

  // file picker
  document.addEventListener("change", function (e) {
    var input = e.target;
    if (!input.classList.contains("att-file")) return;
    var file = input.files[0];
    if (!file) return;
    upload(input.dataset.note, file, function () { input.value = ""; });
  });

  // Ctrl+V paste target = the last hovered note
  var activeNoteId = null;
  document.addEventListener("mouseover", function (e) {
    var item = e.target.closest(".note-item");
    if (item) {
      var input = item.querySelector(".att-file");
      if (input) activeNoteId = input.dataset.note;
    }
  });

  document.addEventListener("paste", function (e) {
    if (!activeNoteId) return;
    var items = e.clipboardData && e.clipboardData.items;
    if (!items) return;
    for (var i = 0; i < items.length; i++) {
      if (items[i].type.indexOf("image") === -1) continue;
      var file = items[i].getAsFile();
      if (!file) continue;
      e.preventDefault();
      upload(activeNoteId, file);
      break;
    }
  });

  // delete
  document.addEventListener("click", function (e) {
    var btn = e.target.closest(".att-del");
    if (!btn) return;
    if (!confirm("Remove this attachment?")) return;
    fetch("/notes/" + btn.dataset.note + "/attachments/" + btn.dataset.att + "/delete", { method: "POST" })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (!data.ok) { alert("Delete failed"); return; }
        var thumb = document.getElementById("att-" + btn.dataset.att);
        if (thumb) thumb.remove();
      });
  });
})();

import gradio as gr
import os
import shutil
from PIL import Image
from PIL.ExifTags import TAGS
from tkinter import Tk, filedialog

# === Глобальные переменные ===
image_list = []
current_index = 0
input_folder = ""
out_folder = {}

# === Функции ===
def prepare_folders(folder):
    global out_folder
    out_folder = {
        "discard": os.path.join(folder, "Отбраковать"),
        "fix": os.path.join(folder, "Нужно_поправить"),
        "perfect": os.path.join(folder, "Идеально")
    }
    for path in out_folder.values():
        os.makedirs(path, exist_ok=True)


def get_metadata(image_path):
    try:
        image = Image.open(image_path)
        info = image.info
        exif_data = image.getexif()
        metadata = ""
        for tag_id, value in exif_data.items():
            tag = TAGS.get(tag_id, tag_id)
            metadata += f"{tag}: {value}\n"
        for k, v in info.items():
            metadata += f"{k}: {v}\n"
        return metadata.strip() or "Нет доступных метаданных"
    except Exception as e:
        return f"Ошибка чтения метаданных: {e}"


def load_image():
    global current_index, image_list, input_folder
    if current_index < len(image_list):
        filename = image_list[current_index]
        full_path = os.path.join(input_folder, filename)
        metadata = get_metadata(full_path)
        progress = f"Изображение {current_index + 1} из {len(image_list)}"
        return full_path, metadata, progress
    else:
        return None, "Изображения закончились!", "Готово!"


def classify_image(action):
    global current_index, image_list, input_folder
    if current_index >= len(image_list):
        return None, "Изображения закончились!", "Готово!"

    filename = image_list[current_index]
    src = os.path.join(input_folder, filename)
    dest = os.path.join(out_folder[action], filename)

    try:
        shutil.move(src, dest)
    except Exception as e:
        return None, f"Ошибка перемещения: {e}", "Ошибка!"

    current_index += 1
    return load_image()


def select_folder_gui():
    Tk().withdraw()  # скрыть окно Tkinter
    folder_selected = filedialog.askdirectory()
    return folder_selected


def select_folder(folder):
    global input_folder, image_list, current_index
    input_folder = folder
    image_list = [f for f in os.listdir(input_folder) if f.lower().endswith(('png', 'jpg', 'jpeg', 'webp'))]
    current_index = 0
    prepare_folders(input_folder)
    return load_image()

# === HTML для горячих клавиш и полноэкранного режима ===
shortcut_html = """
<script>
function shortcuts(e) {
    var event = document.all ? window.event : e;
    if (e.target.tagName.toLowerCase() === 'input' || e.target.tagName.toLowerCase() === 'textarea') return;
    switch (e.key.toLowerCase()) {
        case 'q':
            document.querySelector('.discard-btn')?.click();
            break;
        case 'w':
            document.querySelector('.fix-btn')?.click();
            break;
        case 'e':
            document.querySelector('.perfect-btn')?.click();
            break;
    }
}
document.addEventListener('keydown', shortcuts, false);

function toggleFullscreen() {
  let el = document.querySelector('#image_preview img');
  if (!el) return;
  if (!document.fullscreenElement) {
    el.requestFullscreen().catch(err => alert(`Ошибка: ${err.message}`));
  } else {
    document.exitFullscreen();
  }
}

setTimeout(() => {
 let img = document.querySelector('#image_preview img');
 if (img) {
   img.addEventListener('click', toggleFullscreen);
 }
}, 2000);
</script>
"""

# === Интерфейс ===
with gr.Blocks(head="""
<style>
#image_preview img {
    max-width: 100%;
    max-height: 90vh;
    height: auto;
    object-fit: contain;
    display: block;
    margin: auto;
    cursor: zoom-in;
}

.fullscreen #image_preview img {
    width: 100vw;
    height: 100vh;
    object-fit: contain;
    cursor: zoom-out;
}
</style>
""" + shortcut_html) as app:

    with gr.Row():
        with gr.Column(scale=2):
            image_box = gr.Image(
                label="",
                show_label=False,
                show_download_button=False,
                show_share_button=False,
                container=True,
                elem_id="image_preview"
            )
        with gr.Column(scale=1):
            folder_input = gr.Textbox(label="Укажи путь к папке с изображениями")
            gui_select_btn = gr.Button("Выбрать папку через проводник")
            load_btn = gr.Button("Загрузить изображения")

            metadata_box = gr.Textbox(label="Метаданные", lines=20)
            progress_text = gr.Label("Прогресс")

            discard_btn = gr.Button("Отбраковать (Q)", elem_classes=["discard-btn"], variant="stop")
            fix_btn = gr.Button("Нужно поправить (W)", elem_classes=["fix-btn"], variant="secondary")
            perfect_btn = gr.Button("Идеально (E)", elem_classes=["perfect-btn"], variant="primary")

    gui_select_btn.click(lambda: select_folder_gui(), None, folder_input)
    load_btn.click(lambda folder: select_folder(folder.strip()), inputs=[folder_input], outputs=[image_box, metadata_box, progress_text])
    discard_btn.click(lambda: classify_image("discard"), outputs=[image_box, metadata_box, progress_text])
    fix_btn.click(lambda: classify_image("fix"), outputs=[image_box, metadata_box, progress_text])
    perfect_btn.click(lambda: classify_image("perfect"), outputs=[image_box, metadata_box, progress_text])

app.launch()

import tkinter as tk
from tkinterdnd2 import DND_FILES, TkinterDnD
from tkinter import filedialog
import os
import threading
import queue
from pydub import AudioSegment
import noisereduce as nr
import moviepy.editor as mp

# 全局变量
task_queue = queue.Queue()
tasks = {}
tasks_lock = threading.Lock()


def update_status(task_id, status):
    with tasks_lock:
        tasks[task_id]['status'] = status
    root.after(0, update_task_list)


def extract_audio_from_video(video_path, task_id):
    update_status(task_id, '提取音频')
    video = mp.VideoFileClip(video_path)
    audio_path = video_path.rsplit('.', 1)[0] + ".wav"
    video.audio.write_audiofile(audio_path)
    return audio_path


def reduce_noise(audio_path, output_path, task_id):
    update_status(task_id, '降噪处理中')
    audio = AudioSegment.from_file(audio_path)
    samples = audio.get_array_of_samples()
    sample_rate = audio.frame_rate
    reduced_noise = nr.reduce_noise(y=samples, sr=sample_rate)
    reduced_audio = audio._spawn(reduced_noise)
    reduced_audio.export(output_path, format="wav")


def merge_audio_video(video_path, audio_path, output_video_path, task_id):
    update_status(task_id, '合并音频视频')
    video = mp.VideoFileClip(video_path)
    audio = mp.AudioFileClip(audio_path)
    final_video = video.set_audio(audio)
    final_video.write_videofile(output_video_path, codec='libx264', audio_codec='aac', bitrate='5000k',
                                audio_bitrate='192k')


def process_video(task_id, video_path):
    try:
        update_status(task_id, '开始处理')

        audio_path = extract_audio_from_video(video_path, task_id)
        clean_audio_path = video_path.rsplit('.', 1)[0] + "_clean.wav"
        reduce_noise(audio_path, clean_audio_path, task_id)
        output_video_path = video_path.rsplit('.', 1)[0] + "_reduceNoise.mp4"
        merge_audio_video(video_path, clean_audio_path, output_video_path, task_id)
        os.remove(audio_path)
        os.remove(clean_audio_path)

        update_status(task_id, '已完成')
    except Exception as e:
        update_status(task_id, f'错误: {e}')
    finally:
        task_queue.task_done()


def task_manager():
    while True:
        task_id, video_path = task_queue.get()
        threading.Thread(target=process_video, args=(task_id, video_path)).start()


def add_task(file_path):
    task_id = len(tasks) + 1
    with tasks_lock:
        tasks[task_id] = {'file': file_path, 'status': '等待中'}
    print(f"Adding task {task_id}: {file_path}")  # 调试信息
    task_queue.put((task_id, file_path))
    root.after(0, update_task_list)


def on_drop(event):
    files = event.data.strip('{}').split('} {')
    for file_path in files:
        if os.path.isfile(file_path):
            add_task(file_path)


def select_file():
    file_paths = filedialog.askopenfilenames(filetypes=[("Video files", "*.mp4")])
    for file_path in file_paths:
        add_task(file_path)


def update_task_list():
    for widget in task_list_frame.winfo_children():
        widget.destroy()
    with tasks_lock:
        for task_id, task in tasks.items():
            print(f"Updating task {task_id}: {task['file']} - {task['status']}")  # 调试信息
            status_color = {'等待中': 'orange', '提取音频': 'blue', '降噪处理中': 'blue', '合并音频视频': 'blue',
                            '已完成': 'green', '错误': 'red'}.get(task['status'], 'black')
            task_text = f"任务 {task_id}: {task['file']} - {task['status']}"
            label = tk.Label(task_list_frame, text=task_text, fg=status_color, anchor="w", justify="left",
                             wraplength=650)
            label.pack(fill='x', pady=2)


def create_gui():
    global task_list_frame, root
    root = TkinterDnD.Tk()
    root.title("Video Noise Reduction")
    root.geometry("700x600")

    label = tk.Label(root, text="Drag and drop video files here or click the button to select files", wraplength=650)
    label.pack(pady=20)

    drop_area = tk.Label(root, text="Drop video files here", bg="lightgrey", width=90, height=10)
    drop_area.pack(pady=10)

    drop_area.drop_target_register(DND_FILES)
    drop_area.dnd_bind('<<Drop>>', on_drop)

    button = tk.Button(root, text="Select Files", command=select_file)
    button.pack(pady=10)

    task_list_frame = tk.Frame(root)
    task_list_frame.pack(fill='both', expand=True, pady=20)

    threading.Thread(target=task_manager, daemon=True).start()

    root.mainloop()


if __name__ == "__main__":
    create_gui()

# Импорты
import random
import asyncio
import base64
import aiohttp
import time
import os

URL = "http://localhost:7860/sdapi/v1/"

async def track_progress(session):
    flag = False
    while True:
        await asyncio.sleep(0.5)
        try:
            async with session.get(URL+"progress") as resp:
                progress = await resp.json()
                percent = progress.get("progress", 0) * 100
                step = progress.get("state", {}).get("sampling_step", 0)
                total = progress.get("state", {}).get("sampling_steps", '?')

                print(f"Progress: {percent:.1f}% ({step}/{total})", end='\r')
                if percent >= 100 or progress.get("state", {}).get("job_count", 0) == 0:
                    if not flag:
                        flag = True
                        continue
                    print("\nGeneration complete.")
                    break
        except Exception as e:
            print(f"Generation error: {e}")
            break

async def generate_image(prompt, negative_prompt, width = 896, height = 1440, steps = 40):
    payload = {
        "prompt": prompt,
        "negative_prompt": negative_prompt + "watermark, author tag, Patreon, bad quality, worst quality, worst detail, sketch, censor,",
        "steps": steps,
        "sampler_name": "DPM++ 2M",
        "cfg_scale": 7,
        "width": width,
        "height": height
    }
    async with aiohttp.ClientSession() as session:
        progress_task = asyncio.create_task(track_progress(session))
        async with session.post(URL+"txt2img", json=payload) as response:
            result = await response.json()
        await progress_task
        if "images" in result:
            return result["images"]
        else:
            print("Error in image generation:", result)
            return None

def save_image(image, filename, folder=""):
    if folder:
        if not os.path.exists(folder):
            os.makedirs(folder)
        filename = os.path.join(folder, filename)
    if image is None:
        print("No image to save.")
        return
    with open(filename + ".png", "wb") as f:
        f.write(base64.b64decode(image))


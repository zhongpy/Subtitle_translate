import os
import re
import logging
import math
from pathlib import Path
from google.cloud import translate_v3beta1 as translate
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import os

os.environ["HTTP_PROXY"] = "http://127.0.0.1:10809"

TRANSLATED_LOG_PATH = Path("./logs/translated.log")
LOG_DIR = Path("./logs")

# 配置日志记录
logging.basicConfig(
    filename="frontend.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# 创建日志目录
LOG_DIR.mkdir(exist_ok=True)

# 初始化 Google Translate 客户端
def initialize_google_translate_client():
    client = translate.TranslationServiceClient()
    project_id = "elated-emitter-384907"  # 替换为你的项目ID
    location = "global"  # 使用 global 来支持所有区域
    return client, f"projects/{project_id}/locations/{location}"

# 翻译一批字幕文本
def translate_batch_with_google(client, parent, texts):
    try:
        response = client.translate_text(
            request={
                "parent": parent,
                "contents": texts,
                "mime_type": "text/plain",  # 使用纯文本格式
                "source_language_code": "zh",
                "target_language_code": "en",
            }
        )
        # 提取翻译后的文本
        return [translation.translated_text for translation in response.translations]
    except Exception as e:
        # 打印并记录详细的错误信息
        error_details = getattr(e, 'errors', None)
        if error_details:
            for error in error_details:
                logger.error(f"Error code: {error.get('code')}, message: {error.get('message')}")
        logger.error(f"Google translation error: {str(e)}")
        return ["Translation failed"] * len(texts)

# 提取字幕中的文本
def extract_subtitles(file_path):
    """
    提取字幕中的文本，同时记录原始行。
    返回值包括：
    - subtitles: 非空字幕文本列表（用于翻译）。
    - lines: 原始的 SRT 文件行（包含时间轴等）。
    - empty_indices: 空字幕的索引列表。
    """
    subtitles = []
    empty_indices = []
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    for idx, line in enumerate(lines):
        if '-->' in line or line.strip().isdigit():
            continue
        if not line.strip():
            empty_indices.append(len(subtitles))  # 记录空字幕的位置
        subtitles.append(line.strip())
    return subtitles, lines, empty_indices

# 根据翻译后的字幕生成新的SRT文件
def generate_translated_srt(original_lines, translated_subtitles, output_path, empty_indices):
    """
    根据翻译后的字幕生成新的 SRT 文件，同时处理空字幕。
    - original_lines: 原始的 SRT 文件行。
    - translated_subtitles: 翻译后的非空字幕文本。
    - output_path: 输出文件路径。
    - empty_indices: 空字幕的索引列表。
    """
    idx = 0
    with open(output_path, 'w', encoding='utf-8') as f:
        for line in original_lines:
            if '-->' in line or line.strip().isdigit():
                f.write(line)
            elif line.strip():  # 非空字幕
                if idx in empty_indices:  # 如果是空字幕位置
                    f.write("\n")  # 插入空行
                else:
                    f.write(translated_subtitles[idx] + '\n')
                    idx += 1
            else:
                f.write('\n')
    logger.info(f"Translated file written to: {output_path}")

# 批量翻译字幕
def batch_translate(texts, client, parent, batch_size=100):
    num_batches = math.ceil(len(texts) / batch_size)
    translated_texts = []

    for i in range(num_batches):
        batch = texts[i * batch_size:(i + 1) * batch_size]
        logger.info(f"Translating batch {i + 1}/{num_batches}...")
        translated_batch = translate_batch_with_google(client, parent, batch)
        translated_texts.extend(translated_batch)
    return translated_texts

# 处理单个字幕文件
def process_file(file_path, client, parent, batch_size=100):
    """
    翻译并重新合成单个 SRT 文件。
    """
    try:
        # 提取字幕
        subtitles, original_lines, empty_indices = extract_subtitles(file_path)

        # 翻译非空字幕
        translated_subtitles = batch_translate(subtitles, client, parent, batch_size)

        # 生成翻译后的 SRT 文件
        output_path = str(file_path).replace("zh_hans", "en")
        generate_translated_srt(original_lines, translated_subtitles, output_path, empty_indices)

        return f"Processed {file_path}"
    except Exception as e:
        logger.error(f"Error processing {file_path}: {e}")
        return f"Failed {file_path}"

# 处理文件夹中的所有字幕文件
def process_all_files(folder_path, client, parent, batch_size=100, max_workers=4):
    folder_path = Path(folder_path)
    tasks = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for serial_folder in folder_path.iterdir():
            if serial_folder.is_dir():
                zh_folder = serial_folder / "zh_hans"
                en_folder = serial_folder / "en"
                en_folder.mkdir(exist_ok=True)

                for srt_file in zh_folder.glob("*.srt"):
                    tasks.append(
                        executor.submit(process_file, srt_file, client, parent, batch_size)
                    )

        # 使用进度条跟踪任务
        for future in tqdm(as_completed(tasks), total=len(tasks), desc="Translating files"):
            result = future.result()
            logger.info(result)

if __name__ == "__main__":
    client, parent = initialize_google_translate_client()

    folder_to_process = r'F:\Subtitle'
    logger.info(f"Starting batch subtitle processing in folder: {folder_to_process}")
    process_all_files(folder_to_process, client, parent, batch_size=100, max_workers=4)
    logger.info("Batch subtitle processing completed.")

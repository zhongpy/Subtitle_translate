import os
import re
import logging
import math
from pathlib import Path
from google.cloud import translate
import traceback

os.environ["HTTP_PROXY"] = "http://127.0.0.1:10809"
os.environ["HTTPS_PROXY"] = "http://127.0.0.1:10809"

# 配置日志记录
LOG_DIR = Path("./logs")
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    filename=LOG_DIR / "translation.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# 初始化 Google Translate 客户端
def initialize_google_translate_client():
    client = translate.TranslationServiceClient()
    project_id = "elated-emitter-384907"  # 替换为你的项目ID
    location = "global"
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
        logger.error(f"Google translation error: {e}")
        logger.error("Exception details:", exc_info=True)  # 打印完整堆栈
        if hasattr(e, 'details'):
            logger.error(f"Error details: {e.details()}")
        return ["Translation failed"] * len(texts)

# 提取字幕中的文本
def extract_subtitles(file_path):
    subtitles = []
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    for line in lines:
        if '-->' in line or line.strip().isdigit():
            continue
        subtitles.append(line.strip())
    return subtitles, lines

# 根据翻译后的字幕生成新的SRT文件
def generate_translated_srt(original_lines, translated_subtitles, output_path):
    idx = 0
    with open(output_path, 'w', encoding='utf-8') as f:
        for line in original_lines:
            if '-->' in line or line.strip().isdigit():
                f.write(line)
            elif line.strip():
                f.write(translated_subtitles[idx] + '\n')
                idx += 1
            else:
                f.write('\n')
    logger.info(f"Translated file written to: {output_path}")

# 批量翻译字幕
def batch_translate(texts, client, parent, batch_size=100):
    MAX_TEXT_LENGTH = 5000
    translated_texts = []
    num_batches = math.ceil(len(texts) / batch_size)

    for i in range(num_batches):
        batch = texts[i * batch_size:(i + 1) * batch_size]
        # 截断过长的文本
        batch = [text[:MAX_TEXT_LENGTH] for text in batch]

        logger.info(f"Translating batch {i + 1}/{num_batches}...")
        translated_batch = translate_batch_with_google(client, parent, batch)
        translated_texts.extend(translated_batch)
    return translated_texts

# 处理每个字幕文件
def process_file(file_path, client, parent, batch_size=100):
    try:
        subtitles, original_lines = extract_subtitles(file_path)
        if not subtitles:
            logger.warning(f"No subtitles found in: {file_path}")
            return

        translated_subtitles = batch_translate(subtitles, client, parent, batch_size)
        output_path = file_path.replace("zh_hans", "en")
        generate_translated_srt(original_lines, translated_subtitles, output_path)
    except Exception as e:
        logger.error(f"Error processing {file_path}: {e}")
        logger.error("Exception details:", exc_info=True)

# 处理文件夹中的所有字幕文件
def process_all_files(folder_path, client, parent, batch_size=100):
    folder_path = Path(folder_path)
    for serial_folder in folder_path.iterdir():
        if serial_folder.is_dir():
            zh_folder = serial_folder / "zh_hans"
            en_folder = serial_folder / "en"
            en_folder.mkdir(exist_ok=True)

            for srt_file in zh_folder.glob("*.srt"):
                process_file(srt_file, client, parent, batch_size)

# 示例测试翻译
def test_translation():
    client, parent = initialize_google_translate_client()
    texts = ["你好", "世界"]
    try:
        response = client.translate_text(
            request={
                "parent": parent,
                "contents": texts,
                "mime_type": "text/plain",
                "source_language_code": "zh",
                "target_language_code": "en",
            }
        )
        translated_texts = [translation.translated_text for translation in response.translations]
        print("Translated texts:", translated_texts)
    except Exception as e:
        logger.error(f"Translation failed: {e}", exc_info=True)

if __name__ == "__main__":
    try:
        client, parent = initialize_google_translate_client()

        folder_to_process = r'F:\Subtitle'  # 替换为实际的字幕文件夹路径
        logger.info(f"Starting batch subtitle processing in folder: {folder_to_process}")
        process_all_files(folder_to_process, client, parent, batch_size=100)
        logger.info("Batch subtitle processing completed.")
    except Exception as e:
        logger.error(f"Critical error: {e}")
        logger.error("Exception details:", exc_info=True)

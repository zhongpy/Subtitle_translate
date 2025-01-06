import os
import logging
import math
from pathlib import Path
os.environ["HTTP_PROXY"] = "http://127.0.0.1:10809"
os.environ["HTTPS_PROXY"] = "http://127.0.0.1:10809"
from google.cloud import translate_v3beta1 as translate

# 配置日志
LOG_DIR = "./logs"
os.makedirs(LOG_DIR, exist_ok=True)
logging.basicConfig(
    filename=f"{LOG_DIR}/translation.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
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
    texts = [text for text in texts if text.strip()]  # 过滤空字符串
    if not texts:
        logger.error("Translation batch is empty after filtering.")
        return []

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
        return [translation.translated_text for translation in response.translations]
    except Exception as e:
        logger.error(f"Google translation error: {e}", exc_info=True)
        return ["Translation failed"] * len(texts)

# 提取字幕中的文本
def extract_subtitles(file_path):
    subtitles = []
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    for line in lines:
        if '-->' in line or line.strip().isdigit():
            continue
        if line.strip():  # 只保留非空行
            subtitles.append(line.strip())
    return subtitles, lines

# 批量翻译字幕
def batch_translate(texts, client, parent, batch_size=100):
    num_batches = math.ceil(len(texts) / batch_size)
    translated_texts = []

    for i in range(num_batches):
        batch = texts[i * batch_size:(i + 1) * batch_size]
        logger.info(f"Translating batch {i + 1}/{num_batches}...")

        empty_texts = [text for text in batch if not text.strip()]
        if empty_texts:
            logger.warning(f"Batch {i + 1} contains empty texts: {empty_texts}")

        translated_batch = translate_batch_with_google(client, parent, batch)
        translated_texts.extend(translated_batch)
    return translated_texts

# 处理每个字幕文件
def process_file(file_path, client, parent, batch_size=100):
    subtitles, original_lines = extract_subtitles(file_path)

    # 批量翻译
    translated_subtitles = batch_translate(subtitles, client, parent, batch_size)

    # 修正输出路径，将 "zh_hans" 替换为 "en"
    output_path = str(file_path).replace("zh_hans", "en")
    output_path = Path(output_path)  # 确保输出路径是 Path 对象

    # 创建目标目录（如果不存在）
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 写入翻译后的文件
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


# 处理文件夹中的所有字幕文件
def process_all_files(folder_path, client, parent, batch_size=100):
    folder_path = Path(folder_path)
    for serial_folder in folder_path.iterdir():
        if serial_folder.is_dir():
            zh_folder = serial_folder / "zh_hans"
            en_folder = serial_folder / "en"
            en_folder.mkdir(exist_ok=True)

            for srt_file in zh_folder.glob("*.srt"):
                try:
                    process_file(srt_file, client, parent, batch_size)
                except Exception as e:
                    logger.error(f"Error processing {srt_file}: {e}", exc_info=True)

if __name__ == "__main__":
    client, parent = initialize_google_translate_client()
    folder_to_process = r'F:\Subtitle'
    logger.info(f"Starting batch subtitle processing in folder: {folder_to_process}")
    process_all_files(folder_to_process, client, parent, batch_size=100)
    logger.info("Batch subtitle processing completed.")

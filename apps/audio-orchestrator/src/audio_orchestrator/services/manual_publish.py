import asyncio
import logging
from shared_schemas.commands import RecognizeCommand, EnhanceCommand
from shared_messaging.producer import RabbitMQProducer
from audio_api.cores.config import settings

# Cấu hình log để thấy kết quả
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def trigger_manual_chunk():
    JOB_ID = "f1d293b0-4d54-4b72-bda3-0e9be194884b"
    CHUNK_INDEX = 16
    INPUT_PATH = f"segments/{JOB_ID}/chunk_00{CHUNK_INDEX}.wav"

    # 2. Khởi tạo Producer
    logger.info("Connecting to RabbitMQ...")
    producer = RabbitMQProducer(settings.RABBITMQ_URL)
    await producer.connect()

    # 3. Tạo Command
    # Lưu ý: start_ms/end_ms chỉ để hiển thị, nếu không nhớ có thể để 0
    command = EnhanceCommand(
        job_id=JOB_ID,
        index=CHUNK_INDEX,
        s3_path=INPUT_PATH,
        start_ms=0,
        end_ms=0,
    )

    logger.info(f"Sending Recognize Command for Chunk {CHUNK_INDEX}...")
    await producer.publish(
        exchange_name="audio_ops",
        routing_key="cmd.enhance",
        message=command
    )

    logger.info("Command sent successfully.")
    await producer.close()


if __name__ == "__main__":
    asyncio.run(trigger_manual_chunk())
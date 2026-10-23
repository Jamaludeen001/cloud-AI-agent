# app/services/dynamo_logger.py
import boto3
import os
import time
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Initialize DynamoDB client (uses ECS Task Role credentials automatically)
dynamodb = boto3.resource('dynamodb', region_name=os.getenv("AWS_REGION", "us-east-1"))
table_name = os.getenv("DYNAMODB_TABLE_NAME", "AgentChatLogs")
table = dynamodb.Table(table_name)

def log_chat_to_dynamo(
    session_id: str, 
    run_id: str, 
    question: str, 
    answer: str, 
    duration_ms: float, 
    route: str, 
    status: str
):
    """
    Writes the chat interaction to DynamoDB.
    This runs in the background and will not block the API response.
    """
    try:
        timestamp = datetime.now(timezone.utc).isoformat()
        
        table.put_item(
            Item={
                'session_id': session_id,     # Partition Key
                'timestamp': timestamp,       # Sort Key
                'run_id': run_id,
                'question': question,
                'answer': answer,
                'duration_ms': int(duration_ms),
                'route': route,
                'status': status,
                # Optional: Auto-delete this log after 30 days to save storage costs
                'ttl': int(time.time()) + (30 * 24 * 60 * 60) 
            }
        )
        logger.info(f"[dynamo] Successfully logged chat for session {session_id}")
    except Exception as e:
        # We catch the error so a DB failure never crashes the background task
        logger.error(f"[dynamo] Failed to log chat: {e}")

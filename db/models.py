from sqlalchemy import Column, String, Integer, Boolean, Text, UniqueConstraint, Float, ForeignKey
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
    )

    id = Column(Integer, primary_key=True)
    email = Column(String(255), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    gmail_email = Column(String(255), nullable=False)  # Gmail account email
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(String(50), nullable=False, default="")
    updated_at = Column(String(50), nullable=False, default="")


class UserCredentials(Base):
    __tablename__ = "user_credentials"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_user_credentials_user_id"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    credentials_json = Column(Text, nullable=False)  # Encrypted credentials.json content
    token_json = Column(Text, nullable=False, default="")  # Encrypted token.json content
    created_at = Column(String(50), nullable=False, default="")
    updated_at = Column(String(50), nullable=False, default="")


class EmailMemory(Base):
    __tablename__ = "email_memory"
    __table_args__ = (
        UniqueConstraint("user_id", "email_id", name="uq_email_memory_user_email"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    email_id = Column(String(255), nullable=False)
    sender = Column(String(255), nullable=False)
    sender_type = Column(String(50), nullable=False)
    promo = Column(Boolean, nullable=False, default=False)
    urgency = Column(String(50), nullable=False, default="")
    subject = Column(String(255), nullable=False, default="")
    body = Column(Text, nullable=False, default="")
    timestamp = Column(String(50), nullable=False, default="")
    priority_label = Column(String(50), nullable=False, default="")
    priority_confidence = Column(Float, nullable=False, default=0.0)
    priority_score = Column(Integer, nullable=False, default=0)
    priority_reasons = Column(Text, nullable=False, default="")
    priority_tier = Column(String(50), nullable=False, default="")
    decision_timestamp = Column(String(50), nullable=False, default="")
    reply_draft = Column(Text, nullable=False, default="")
    reply_timestamp = Column(String(50), nullable=False, default="")
    next_action = Column(String(50), nullable=False, default="")
    action_reason = Column(Text, nullable=False, default="")
    task_status = Column(String(50), nullable=False, default="")
    urgent_flag = Column(Boolean, nullable=False, default=False)
    needs_human_review = Column(Boolean, nullable=False, default=False)
    action_timestamp = Column(String(50), nullable=False, default="")


class RetryQueue(Base):
    __tablename__ = "retry_queue"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    email_id = Column(String(255), nullable=False)
    operation = Column(String(50), nullable=False, default="analyze_and_execute")
    payload = Column(Text, nullable=False, default="")
    status = Column(String(50), nullable=False, default="pending")
    attempts = Column(Integer, nullable=False, default=0)
    next_retry_at = Column(String(50), nullable=False, default="")
    last_error = Column(Text, nullable=False, default="")
    created_at = Column(String(50), nullable=False, default="")
    updated_at = Column(String(50), nullable=False, default="")


class TaskQueue(Base):
    __tablename__ = "task_queue"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    email_id = Column(String(255), nullable=False)
    title = Column(String(255), nullable=False, default="")
    description = Column(Text, nullable=False, default="")
    status = Column(String(50), nullable=False, default="open")
    created_at = Column(String(50), nullable=False, default="")
    updated_at = Column(String(50), nullable=False, default="")


class BehaviorLog(Base):
    __tablename__ = "behavior_log"
    __table_args__ = (
        UniqueConstraint("user_id", "email_id", name="uq_behavior_log_user_email"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    email_id = Column(String(255), nullable=False)
    intent = Column(String(255), nullable=False, default="")
    sender_domain = Column(String(255), nullable=False, default="")
    requires_reply = Column(Boolean, nullable=False, default=False)
    user_final_action = Column(String(255), nullable=False, default="")
    user_opened = Column(Boolean, nullable=False, default=False)
    proposed_action = Column(String(255), nullable=False, default="")
    agent_action = Column(String(255), nullable=False, default="")
    llm_confidence = Column(Float, nullable=False, default=0.0)
    behavior_match_score = Column(Float, nullable=False, default=0.0)
    final_decision_score = Column(Float, nullable=False, default=0.0)
    created_at = Column(String(50), nullable=False, default="")
    updated_at = Column(String(50), nullable=False, default="")

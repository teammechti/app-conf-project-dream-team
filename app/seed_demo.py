from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import select

from app.db.database import SessionLocal
from app.models.entities import OrganizerSettings, Participant, ParticipantStatus, Queue, QueueStatus, QueueTemplate


def seed_demo() -> None:
    db = SessionLocal()
    try:
        if db.get(OrganizerSettings, 1) is None:
            db.add(OrganizerSettings(id=1))
        if not db.scalar(select(QueueTemplate.id).limit(1)):
            db.add_all([
                QueueTemplate(name="Защита лабораторных работ", description="Шаблон для проведения защиты лабораторных работ.", location="Ауд. 401", default_start_time=time(10), default_end_time=time(18), max_participants=25, participant_instruction="Возьмите отчёт и будьте готовы ответить на вопросы."),
                QueueTemplate(name="Приём документов", description="Шаблон для приёма заявлений и документов.", location="Ауд. 101", default_start_time=time(9), default_end_time=time(17), max_participants=50),
                QueueTemplate(name="Консультация преподавателя", description="Индивидуальные консультации по курсовым работам.", location="Ауд. 305", default_start_time=time(14), default_end_time=time(16), max_participants=15, show_participant_list=False),
            ])
        db.commit()
        if db.scalar(select(Queue.id).where(Queue.public_code == "it-lab")):
            return
        now = datetime.now(timezone.utc)
        queue = Queue(
            public_code="it-lab",
            management_token="demo-management-token",
            name="Защита лабораторных работ",
            description="Очередь для сдачи и защиты лабораторных работ по курсу ИТ.",
            location="Ауд. 401, факультет ИТ",
            date=date.today(),
            start_time=time(10, 0),
            end_time=time(18, 0),
            max_participants=50,
            allow_join_after_start=True,
            show_participant_list=True,
            participant_instruction="Подготовьтесь, пожалуйста, к входу в аудиторию.",
            status=QueueStatus.active,
            started_at=now - timedelta(hours=2),
        )
        db.add(queue)
        db.flush()
        names = ["Анна Орлова", "Павел Соколов", "Елена Морозова", "Михаил Волков", "Дарья Козлова", "Иван Петров", "Максим Сидоров", "Олег Кузнецов", "Алексей Волков", "Мария Смирнова", "Егор Никитин"]
        for index, name in enumerate(names, 1):
            joined = now - timedelta(minutes=75-index*4)
            status = ParticipantStatus.completed if index <= 5 else ParticipantStatus.called if index == 6 else ParticipantStatus.waiting
            participant = Participant(
                queue_id=queue.id,
                number=f"A-{index:03d}", name=name, token=f"demo-participant-{index}",
                status=status, queue_order=index, joined_at=joined,
                called_at=joined + timedelta(minutes=8+index) if index <= 6 else None,
                completed_at=joined + timedelta(minutes=14+index) if index <= 5 else None,
            )
            db.add(participant)

        other_queues = [
            ("documents", "Приём документов", "Ауд. 101, Учебный отдел", QueueStatus.active, 8, 21),
            ("consultation", "Консультация преподавателя", "Ауд. 305, факультет ИТ", QueueStatus.paused, 6, 9),
            ("event-registration", "Регистрация на мероприятие", "Онлайн", QueueStatus.finished, 0, 18),
        ]
        for code, name, location, status, waiting, completed in other_queues:
            q = Queue(
                public_code=code, management_token=f"manage-{code}", name=name,
                description="Учебная демонстрационная очередь.", location=location, date=date.today(),
                start_time=time(9,0), end_time=time(17,0), max_participants=80,
                allow_join_after_start=True, show_participant_list=True,
                participant_instruction="Ожидайте вызова на этой странице.", status=status,
                started_at=now-timedelta(hours=3), finished_at=now if status == QueueStatus.finished else None,
            )
            db.add(q); db.flush()
            for idx in range(1, waiting+completed+1):
                joined = now - timedelta(minutes=(waiting+completed-idx+1)*3)
                p_status = ParticipantStatus.completed if idx <= completed else ParticipantStatus.waiting
                db.add(Participant(queue_id=q.id, number=f"A-{idx:03d}", name=f"Участник {idx}", token=f"{code}-{idx}", status=p_status, queue_order=idx, joined_at=joined, called_at=joined+timedelta(minutes=9) if p_status == ParticipantStatus.completed else None, completed_at=joined+timedelta(minutes=14) if p_status == ParticipantStatus.completed else None))
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    seed_demo()

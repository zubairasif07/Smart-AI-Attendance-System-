import cv2
import face_recognition
from pathlib import Path


def capture_face_images(name: str, roll_no: str, student_folder: Path, num_images: int = 30):
    """Capture face images from webcam and store them under a student dataset folder.
    
    The camera window closes automatically once all required images are captured.
    No manual key press is needed.
    """
    student_folder.mkdir(parents=True, exist_ok=True)
    camera = cv2.VideoCapture(0)
    if not camera.isOpened():
        raise RuntimeError("Unable to access webcam. Make sure a camera is connected.")

    count = 0
    try:
        while count < num_images:
            ret, frame = camera.read()
            if not ret:
                break

            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            face_locations = face_recognition.face_locations(rgb_frame, model="hog")

            if face_locations:
                top, right, bottom, left = face_locations[0]
                face_image = frame[top:bottom, left:right]
                try:
                    face_image = cv2.resize(face_image, (250, 250))
                except cv2.error:
                    continue
                gray_face = cv2.cvtColor(face_image, cv2.COLOR_BGR2GRAY)
                image_path = student_folder / f"{roll_no}_{count + 1}.jpg"
                cv2.imwrite(str(image_path), gray_face)
                count += 1

                # Draw capture feedback
                cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
                cv2.putText(
                    frame,
                    f"Capturing: {count}/{num_images}",
                    (left, top - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 0),
                    2,
                )

                # Progress bar at bottom
                bar_w = frame.shape[1]
                filled = int(bar_w * count / num_images)
                cv2.rectangle(frame, (0, frame.shape[0] - 8), (filled, frame.shape[0]), (0, 255, 0), -1)
                cv2.rectangle(frame, (filled, frame.shape[0] - 8), (bar_w, frame.shape[0]), (50, 50, 50), -1)

            else:
                # No face detected — prompt user
                cv2.putText(
                    frame,
                    "Position your face in the frame...",
                    (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.75,
                    (0, 200, 255),
                    2,
                )

            cv2.putText(
                frame,
                f"Registering: {name}",
                (10, frame.shape[0] - 18),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (200, 200, 200),
                1,
            )

            cv2.imshow("Face Dataset Collection — Stay still & look at camera", frame)
            # Allow window to refresh; 'q' still exits early
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

        # ── All images captured: show completion banner then auto-close ──────
        if count >= num_images:
            ret, frame = camera.read()
            if not ret:
                # Use a blank frame if the camera already stopped
                frame = (frame if frame is not None else 
                         __import__('numpy').zeros((480, 640, 3), dtype=__import__('numpy').uint8))
            # Green completion overlay
            overlay = frame.copy()
            cv2.rectangle(overlay, (0, 0), (frame.shape[1], frame.shape[0]), (0, 30, 0), -1)
            cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)
            cv2.putText(
                frame,
                "✓  Registration Complete!",
                (int(frame.shape[1] / 2) - 200, int(frame.shape[0] / 2) - 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.1,
                (0, 255, 120),
                3,
            )
            cv2.putText(
                frame,
                f"{num_images} face images saved for {name}",
                (int(frame.shape[1] / 2) - 190, int(frame.shape[0] / 2) + 28),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (180, 255, 180),
                2,
            )
            cv2.putText(
                frame,
                "Camera closing automatically...",
                (int(frame.shape[1] / 2) - 150, int(frame.shape[0] / 2) + 70),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (150, 200, 150),
                1,
            )
            cv2.imshow("Face Dataset Collection — Stay still & look at camera", frame)
            cv2.waitKey(1500)   # Show the success banner for 1.5 s then auto-close

    finally:
        camera.release()
        cv2.destroyAllWindows()

    if count < num_images:
        raise RuntimeError(
            f"Face dataset collection incomplete. Collected {count} of {num_images} images."
        )
    return True

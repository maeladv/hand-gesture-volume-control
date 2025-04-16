import cv2
import mediapipe as mp
import os
import tkinter as tk
import threading
import time  # Import the time module for tracking intervals

x1 = y1 = x2 = y2 = 0
cam = cv2.VideoCapture(0)
my_hands = mp.solutions.hands.Hands()
drawing_utils = mp.solutions.drawing_utils

# Create a Tkinter window for the volume display
root = tk.Tk()
root.title("Volume Display")
root.geometry("200x100")
root.attributes("-topmost", True)  # Keep the window on top
root.overrideredirect(True)  # Remove window decorations (optional)
root.withdraw()  # Hide the window initially

# Label to display the volume
volume_label = tk.Label(root, text="Volume: 0%", font=("Helvetica", 16))
volume_label.pack(expand=True)

# Timer to hide the window
hide_timer = None

last_volume = 0  # Variable to store the last volume value
last_update_time = time.time()  # Timestamp for the last update
volume_threshold = 5  # Define a small threshold for volume variation

stop_flag = threading.Event()  # Create a threading event to signal the thread to stop

def update_volume_label(volume):
    global hide_timer
    volume_label.config(text=f"Volume: {volume}%")
    root.deiconify()  # Show the window
    root.update_idletasks()

    # Cancel the previous timer if it exists
    if hide_timer:
        hide_timer.cancel()

    # Start a new timer to hide the window after 1 second
    hide_timer = threading.Timer(1.0, hide_volume_window)
    hide_timer.start()

def hide_volume_window():
    root.withdraw()  # Hide the window

def process_camera():
    global x1, y1, x2, y2, last_volume, last_update_time
    try:
        while not stop_flag.is_set():  # Check the stop flag in the loop
            ret, image = cam.read()
            if not ret:
                print("Error: Failed to read from camera.")
                break  # Exit the loop if the camera fails

            frame_height, frame_width, _ = image.shape
            output = my_hands.process(image)
            hands = output.multi_hand_landmarks
            if hands:
                for hand in hands:
                    drawing_utils.draw_landmarks(image, hand)
                    landmarks = hand.landmark
                    for id, landmarks in enumerate(landmarks):
                        x = int(landmarks.x * frame_width)
                        y = int(landmarks.y * frame_height)

                        if id == 8:  # Index finger tip
                            x1, y1 = x, y
                        if id == 4:  # Thumb tip
                            x2, y2 = x, y
                dist = ((x1 - x2) ** 2 + (y1 - y2) ** 2) ** 0.5
                max_dist = 300  # Maximum distance (adjust based on your setup)
                volume = int(min(max(dist / max_dist * 100, 0), 100))  # Clamp volume between 0 and 100

                # Check if 0.5 seconds have passed
                current_time = time.time()
                if (current_time - last_update_time) >= 0.3:
                    # Always update the system volume
                    os.system(f"pactl set-sink-volume @DEFAULT_SINK@ {volume}%")

                    # Only update the volume display if the variation is within the threshold
                    if abs(volume - last_volume) <= volume_threshold:
                        root.after(0, update_volume_label, volume)  # Schedule GUI update in the main thread

                    # Update the last volume and timestamp
                    last_volume = volume
                    last_update_time = current_time
    except Exception as e:
        print(f"Error in process_camera: {e}")
    finally:
        cam.release()
        cv2.destroyAllWindows()
        # Signal the main thread to destroy the root window
        stop_flag.set()

# Handle KeyboardInterrupt in the main thread
try:
    # Run the OpenCV loop in a separate thread
    camera_thread = threading.Thread(target=process_camera)
    camera_thread.daemon = True
    camera_thread.start()

    # Replace root.mainloop() with a loop to allow KeyboardInterrupt handling
    while not stop_flag.is_set():
        root.update()  # Process Tkinter events
        time.sleep(0.01)  # Prevent high CPU usage

except KeyboardInterrupt:
    print("Exiting...")
    stop_flag.set()  # Signal the thread to stop
    camera_thread.join()  # Wait for the thread to finish
finally:
    # Destroy the Tkinter root window in the main thread
    if root.winfo_exists():
        root.destroy()
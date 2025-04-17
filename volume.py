import cv2
import mediapipe as mp
import os
import tkinter as tk
import threading
import time  # Import the time module for tracking intervals
import queue  # Import the queue module

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

max_dist = 300

stop_flag = threading.Event()  # Create a threading event to signal the thread to stop

# Create a thread-safe queue for communication between threads
tkinter_queue = queue.Queue()

def update_volume_label(volume):
    global hide_timer
    volume_label.config(text=f"Volume: {volume}%")
    root.deiconify()  # Show the window
    root.update_idletasks()

    # Cancel the previous timer if it exists
    if hide_timer:
        hide_timer.cancel()

    # Start a new timer to send a message to hide the window after 1 second
    hide_timer = threading.Timer(1.0, lambda: tkinter_queue.put(("HIDE_WINDOW",)))
    hide_timer.start()

def hide_volume_window():
    """Hide the Tkinter window (called in the main thread)."""
    root.withdraw()  # Hide the window

def process_camera():
    global x1, y1, x2, y2, last_volume, last_update_time
    distances = []  # List to store recent distances
    max_distances = 5  # Number of distances to average
    smoothing_factor = 0.8  # For smoothing volume changes

    try:
        while not stop_flag.is_set():
            ret, image = cam.read()
            if not ret:
                print("Error: Failed to read from camera.")
                break

            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            output = my_hands.process(image_rgb)
            hands = output.multi_hand_landmarks

            if hands:
                frame_height, frame_width, _ = image.shape
                for hand in hands:
                    drawing_utils.draw_landmarks(image, hand)
                    landmarks = hand.landmark
                    for id, landmark in enumerate(landmarks):
                        x = int(landmark.x * frame_width)
                        y = int(landmark.y * frame_height)

                        if id == 8:  # Index finger tip
                            x1, y1 = x, y
                        if id == 4:  # Thumb tip
                            x2, y2 = x, y

                dist = (((x1 - x2) ** 2 + (y1 - y2) ** 2) ** 0.5)*3

                # Smooth the distance using exponential smoothing
                smoothed_dist = dist
                if distances:
                    smoothed_dist = 0.7 * dist + 0.3 * distances[-1]
                distances.append(smoothed_dist)
                if len(distances) > max_distances:
                    distances.pop(0)

                # Map the smoothed distance to volume
                volume = min(max(smoothed_dist / max_dist * 100, 0), 100)

                # Smooth volume changes
                smoothed_volume = last_volume + (volume - last_volume) * smoothing_factor
                volume = int(smoothed_volume)

                # Update volume if conditions are met
                current_time = time.time()
                if abs(volume - last_volume) >= volume_threshold and (current_time - last_update_time) >= 0.2:
                    os.system(f"pactl set-sink-volume @DEFAULT_SINK@ {volume}%")
                    tkinter_queue.put(("UPDATE_VOLUME", volume))
                    last_volume = volume
                    last_update_time = current_time
    except Exception as e:
        print(f"Error in process_camera: {e}")
    finally:
        cam.release()
        cv2.destroyAllWindows()
        tkinter_queue.put(("STOP_TKINTER",))

def stop_tkinter():
    """Safely stop the Tkinter main loop."""
    if root.winfo_exists():
        root.destroy()

# Main thread loop
try:
    # Run the OpenCV loop in a separate thread
    camera_thread = threading.Thread(target=process_camera)
    camera_thread.daemon = True
    camera_thread.start()

    # Replace root.mainloop() with a loop to allow KeyboardInterrupt handling
    while not stop_flag.is_set():
        root.update()  # Process Tkinter events

        # Check the queue for messages from the camera thread
        try:
            message = tkinter_queue.get_nowait()
            if message[0] == "UPDATE_VOLUME":
                volume = message[1]
                update_volume_label(volume)  # Update the volume label in the main thread
            elif message[0] == "HIDE_WINDOW":
                hide_volume_window()  # Hide the window in the main thread
            elif message[0] == "STOP_TKINTER":
                stop_flag.set()  # Signal the thread to stop
        except queue.Empty:
            pass

        time.sleep(0.01)  # Prevent high CPU usage

except KeyboardInterrupt:
    print("Exiting...")
    stop_flag.set()  # Signal the thread to stop
    camera_thread.join()  # Wait for the thread to finish
finally:
    # Safely destroy the Tkinter root window
    if root.winfo_exists():
        root.destroy()
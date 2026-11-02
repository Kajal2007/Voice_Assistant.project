"""
Voice Control Assistant
-----------------------
A simple desktop assistant that listens to voice commands, shows what it
heard, performs a task, and answers using speech.

Libraries used:
    tkinter           - graphical user interface (comes with Python)
    speech_recognition - converts speech to text
    pyttsx3           - converts text to speech (works offline)
    datetime          - current date and time
    webbrowser        - opens websites
    threading / queue - keep the window responsive while listening
"""

import datetime
import queue
import threading
import tkinter as tk
import webbrowser
from tkinter import ttk

import pyttsx3
import speech_recognition as sr


# ---------------------------------------------------------------------------
# Part 1: Helper functions (no GUI code here, easy to test and explain)
# ---------------------------------------------------------------------------

def speak(text):
    """Say the given text out loud using pyttsx3.

    A new engine is created on every call. This is the most reliable way to
    use pyttsx3 from a background thread on Windows.
    """
    try:
        engine = pyttsx3.init()
        engine.setProperty("rate", 170)  # speaking speed (words per minute)
        engine.say(text)
        engine.runAndWait()
        engine.stop()
    except Exception as error:
        # If speech output fails, the app should keep working (text still shows)
        print(f"Text-to-speech error: {error}")


def get_current_time():
    """Return a friendly sentence with the current time."""
    now = datetime.datetime.now()
    time_text = now.strftime("%I:%M %p").lstrip("0")  # e.g. 3:45 PM
    return f"The time is {time_text}."


def get_current_date():
    """Return a friendly sentence with today's date."""
    now = datetime.datetime.now()
    date_text = f"{now.strftime('%A, %B')} {now.day}, {now.year}"
    return f"Today is {date_text}."


def process_command(command):
    """Decide what to do for a command.

    Returns a tuple: (response_text, should_exit)
    """
    command = command.lower()
    words = command.split()  # split into words so "hi" does not match "this"

    # 1. Exit command
    if "exit" in words or "quit" in words or "goodbye" in words:
        return "Goodbye! Closing the assistant.", True

    # 2. Time command
    if "time" in words:
        return get_current_time(), False

    # 3. Date command
    if "date" in words:
        return get_current_date(), False

    # 4. Open Google
    if "google" in words:
        webbrowser.open("https://www.google.com")
        return "Opening Google.", False

    # 5. Open YouTube
    if "youtube" in words:
        webbrowser.open("https://www.youtube.com")
        return "Opening YouTube.", False

    # 6. Greetings
    if "hello" in words or "hi" in words or "hey" in words:
        return "Hello! How can I help you today?", False

    # 7. Anything else
    return "Sorry, I do not know that command yet.", False


# ---------------------------------------------------------------------------
# Part 2: The GUI application
# ---------------------------------------------------------------------------

class VoiceAssistantApp:
    def __init__(self, root):
        self.root = root
        self.is_listening = False          # prevents two listening sessions at once
        self.message_queue = queue.Queue() # the background thread sends updates here

        self.build_gui()

        # Check the queue every 100 ms. This runs on the main (GUI) thread,
        # so all widget updates are thread-safe.
        self.root.after(100, self.check_queue)

    # ----- GUI layout -------------------------------------------------------

    def build_gui(self):
        """Create all the widgets (labels, buttons, display areas)."""
        self.root.title("Voice Control Assistant")
        self.root.geometry("520x470")
        self.root.resizable(False, False)
        self.root.configure(padx=20, pady=15)

        title_font = ("Segoe UI", 18, "bold")
        normal_font = ("Segoe UI", 11)
        display_font = ("Segoe UI", 12)

        # Title and short introduction
        tk.Label(self.root, text="Voice Control Assistant",
                 font=title_font).pack(pady=(0, 5))
        tk.Label(self.root,
                 text="Click Start Listening and say a command such as\n"
                      "\"Hello\", \"What is the time?\", \"Open Google\" or \"Exit assistant\".",
                 font=normal_font, fg="#555555", justify="center").pack(pady=(0, 12))

        # Listening status indicator
        self.status_label = tk.Label(self.root, text="Status: Ready",
                                     font=("Segoe UI", 11, "bold"), fg="#2e7d32")
        self.status_label.pack(pady=(0, 10))

        # Start Listening button
        self.listen_button = tk.Button(self.root, text="Start Listening",
                                       font=("Segoe UI", 12, "bold"),
                                       bg="#1976d2", fg="white", width=20,
                                       command=self.start_listening)
        self.listen_button.pack(pady=(0, 12))

        # Recognized command display
        command_frame = ttk.LabelFrame(self.root, text=" Recognized Command ")
        command_frame.pack(fill="x", pady=5)
        self.command_label = tk.Label(command_frame, text="-", font=display_font,
                                      wraplength=440, justify="left", anchor="w")
        self.command_label.pack(fill="x", padx=10, pady=8)

        # Assistant response display
        response_frame = ttk.LabelFrame(self.root, text=" Assistant Response ")
        response_frame.pack(fill="x", pady=5)
        self.response_label = tk.Label(response_frame, text="-", font=display_font,
                                       wraplength=440, justify="left", anchor="w")
        self.response_label.pack(fill="x", padx=10, pady=8)

        # Exit button
        tk.Button(self.root, text="Exit", font=normal_font, width=12,
                  bg="#c62828", fg="white",
                  command=self.exit_app).pack(pady=(12, 0))

        # Closing the window with the X button also exits safely
        self.root.protocol("WM_DELETE_WINDOW", self.exit_app)

    # ----- Button actions ---------------------------------------------------

    def start_listening(self):
        """Called when the Start Listening button is clicked."""
        if self.is_listening:  # ignore extra clicks while already listening
            return

        self.is_listening = True
        self.listen_button.config(state="disabled")
        self.command_label.config(text="-")
        self.response_label.config(text="-")

        # Run the listening work in a background thread so the window stays responsive
        worker = threading.Thread(target=self.listen_and_respond, daemon=True)
        worker.start()

    def exit_app(self):
        """Close the application safely."""
        self.root.destroy()

    # ----- Background thread work -------------------------------------------

    def listen_and_respond(self):
        """Listen, recognize, act and speak. Runs in a background thread.

        This method never touches Tkinter widgets directly. It only puts
        messages in the queue, and the main thread updates the GUI.
        """
        recognizer = sr.Recognizer()
        should_exit = False

        try:
            with sr.Microphone() as source:
                self.message_queue.put(("status", "Status: Listening... speak now", "#e65100"))
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = recognizer.listen(source, timeout=5, phrase_time_limit=7)

            self.message_queue.put(("status", "Status: Processing...", "#1565c0"))

            # Send the audio to Google's free speech service (needs internet)
            command = recognizer.recognize_google(audio)
            self.message_queue.put(("command", command))

            response, should_exit = process_command(command)
            self.message_queue.put(("response", response))
            speak(response)

        except sr.WaitTimeoutError:
            self.report_error("I did not hear anything. Please try again.")
        except sr.UnknownValueError:
            self.report_error("Sorry, I could not understand that. Please speak clearly and try again.")
        except sr.RequestError:
            self.report_error("The speech service is not available. Please check your internet connection.")
        except (OSError, AttributeError):
            # OSError: no microphone found. AttributeError: PyAudio is not installed.
            self.report_error("Microphone not available. Please check that a microphone "
                              "is connected and PyAudio is installed.")
        except Exception as error:
            self.report_error(f"Something went wrong: {error}")

        # Tell the main thread we are finished
        if should_exit:
            self.message_queue.put(("exit",))
        else:
            self.message_queue.put(("done",))

    def report_error(self, message):
        """Show an error message in the GUI and read it aloud."""
        self.message_queue.put(("response", message))
        speak(message)

    # ----- Main-thread queue handler ----------------------------------------

    def check_queue(self):
        """Read messages from the background thread and update the GUI."""
        try:
            while True:
                message = self.message_queue.get_nowait()
                kind = message[0]

                if kind == "status":
                    self.status_label.config(text=message[1], fg=message[2])
                elif kind == "command":
                    self.command_label.config(text=message[1])
                elif kind == "response":
                    self.response_label.config(text=message[1])
                elif kind == "done":
                    self.is_listening = False
                    self.listen_button.config(state="normal")
                    self.status_label.config(text="Status: Ready", fg="#2e7d32")
                elif kind == "exit":
                    self.exit_app()
                    return  # window is gone, stop checking
        except queue.Empty:
            pass  # no more messages right now

        self.root.after(100, self.check_queue)  # check again in 100 ms


# ---------------------------------------------------------------------------
# Part 3: Program entry point
# ---------------------------------------------------------------------------

def main():
    root = tk.Tk()
    VoiceAssistantApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

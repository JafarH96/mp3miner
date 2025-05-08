import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re
import tkinter as tk
from tkinter import ttk, messagebox
from pygame import mixer
from urllib.request import urlretrieve
import os
import tempfile
import threading
import json
from datetime import datetime
from PIL import Image, ImageTk

def load_app_icon(root):
    """Load the icon for the given root window"""
    try:
        if os.path.exists('icon.png'):
            return ImageTk.PhotoImage(Image.open('icon.png'))
    except Exception as e:
        print(f"Error loading icon: {e}")
    return None

def load_url_history():
    """Load URL history from JSON file"""
    try:
        if os.path.exists('url_history.json'):
            with open('url_history.json', 'r') as f:
                return json.load(f)
    except:
        pass
    return []

def save_url_history(history):
    """Save URL history to JSON file"""
    try:
        with open('url_history.json', 'w') as f:
            json.dump(history, f)
    except:
        pass

def add_to_history(url):
    """Add URL to history with timestamp"""
    history = load_url_history()
    # Remove if already exists
    history = [h for h in history if h['url'] != url]
    # Add new entry
    history.insert(0, {
        'url': url,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })
    # Keep only last 10 entries
    history = history[:10]
    save_url_history(history)
    return history

def scrape_mp3_urls(url):
    """
    Scrapes all MP3 URLs from a given website
    
    Args:
        url (str): The URL of the website to scrape
        
    Returns:
        list: List of MP3 URLs found on the website
    """
    try:
        # Send GET request to the URL
        response = requests.get(url)
        response.raise_for_status()
        
        # Parse the HTML content
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find all links on the page
        mp3_urls = []
        
        # Look for direct MP3 links in anchor tags
        for link in soup.find_all('a', href=True):
            href = link['href']
            # Make URL absolute if it's relative
            full_url = urljoin(url, href)
            if full_url.lower().endswith('.mp3'):
                mp3_urls.append(full_url)
                
        # Look for MP3 links in source tags
        for source in soup.find_all('source'):
            if source.get('src'):
                src = source['src']
                full_url = urljoin(url, src)
                if full_url.lower().endswith('.mp3'):
                    mp3_urls.append(full_url)
                    
        # Look for MP3 URLs in script tags using regex
        scripts = soup.find_all('script')
        for script in scripts:
            if script.string:
                mp3_matches = re.findall(r'https?://[^\s<>"\']+?\.mp3', script.string)
                mp3_urls.extend(mp3_matches)
        
        # Look for MP3 URLs in data-song attributes (e.g., <span data-song="..."></span>)
        for tag in soup.find_all(attrs={'data-song': True}):
            data_song = tag['data-song']
            full_url = urljoin(url, data_song)
            if full_url.lower().endswith('.mp3'):
                mp3_urls.append(full_url)
        
        return list(set(mp3_urls))  # Remove duplicates
        
    except requests.RequestException as e:
        print(f"Error fetching the webpage: {e}")
        return []
    except Exception as e:
        print(f"An error occurred: {e}")
        return []

# Example usage:
def create_player_ui(mp3_urls):
    """
    Creates a simple UI player for the extracted MP3 files using tkinter
    
    Args:
        mp3_urls (list): List of MP3 URLs to play
    """
    # Initialize pygame mixer
    mixer.init()
    
    # Create temporary directory to store downloaded files
    temp_dir = tempfile.mkdtemp()
    current_track = 0
    is_playing = False
    current_position = 0
    update_thread = None
    current_file = None
    paused_position = 0
    is_seeking = False
    track_length = 100  # Default track length in seconds
    
    def format_time(seconds):
        try:
            seconds = int(seconds)
            m, s = divmod(seconds, 60)
            return f"{m}:{s:02d}"
        except:
            return "0:00"
    
    def get_track_length():
        try:
            if current_file and os.path.exists(current_file):
                import wave
                with wave.open(current_file, 'rb') as wav_file:
                    frames = wav_file.getnframes()
                    rate = wav_file.getframerate()
                    return frames / float(rate)
        except:
            pass
        return 100  # Default length if can't determine
    
    def cleanup_current_file():
        nonlocal current_file
        if current_file and os.path.exists(current_file):
            try:
                mixer.music.unload()
                os.remove(current_file)
            except:
                pass
        current_file = None
    
    def get_track_name(url):
        # Extract filename from URL and clean it up
        filename = os.path.basename(url).replace('.mp3', '')
        
        # Remove URL encoding
        try:
            from urllib.parse import unquote
            filename = unquote(filename)
        except:
            pass
            
        # Remove special characters and keep only letters, numbers, and spaces
        import re
        # Replace underscores and hyphens with spaces
        filename = filename.replace('_', ' ').replace('-', ' ')
        # Keep only letters, numbers, and spaces
        filename = re.sub(r'[^a-zA-Z0-9\s]', '', filename)
        # Remove extra spaces
        filename = ' '.join(filename.split())
        
        # If the filename is empty after cleaning, return a default name
        if not filename:
            return f"Track {current_track + 1}"
            
        return filename
    
    def play_selected_track(event=None):
        nonlocal current_track, is_playing
        selection = track_listbox.curselection()
        if selection:
            current_track = selection[0]
            track_counter.config(text=f"Track {current_track + 1} of {len(mp3_urls)}")
            download_and_play(mp3_urls[current_track])
            is_playing = True
            play_btn.config(image=pause_img)
            play_btn.image = pause_img
            update_progress()
            play_btn.focus_set()  # Set focus to play button
    
    def download_and_play(url):
        nonlocal current_position, current_file, paused_position, track_length
        try:
            # Cleanup previous file if exists
            cleanup_current_file()
            
            # Create new temp file
            current_file = os.path.join(temp_dir, f"track_{current_track}.mp3")
            
            # Download MP3 to temp file
            urlretrieve(url, current_file)
            
            # Get track length
            track_length = get_track_length()
            seeker.config(to=track_length)
            total_time_label.config(text=format_time(track_length))
            
            # Load and play the music
            mixer.music.load(current_file)
            mixer.music.play()
            
            current_position = 0
            paused_position = 0
            progress_var.set(0)
            current_time_label.config(text="0:00")
            update_progress()
            title_label.config(text=get_track_name(url))
            
            # Update listbox selection
            track_listbox.selection_clear(0, tk.END)
            track_listbox.selection_set(current_track)
            track_listbox.see(current_track)
            
        except Exception as e:
            print(f"Error playing track: {e}")
            title_label.config(text="Error playing track")
            cleanup_current_file()
    
    def update_progress():
        nonlocal current_position, update_thread, paused_position
        if is_playing and mixer.music.get_busy() and not is_seeking:
            current_position += 0.1
            paused_position = current_position
            progress_var.set(current_position)
            current_time_label.config(text=format_time(current_position))
            update_thread = threading.Timer(0.1, update_progress)
            update_thread.start()
        else:
            if update_thread:
                update_thread.cancel()
    
    def on_seek_start(event):
        nonlocal is_seeking
        is_seeking = True
        if update_thread:
            update_thread.cancel()
    
    def on_seek_end(event):
        nonlocal is_seeking, current_position, paused_position
        is_seeking = False
        new_position = progress_var.get()
        current_position = new_position
        paused_position = new_position
        
        if current_file and os.path.exists(current_file):
            try:
                # Calculate the position in seconds
                position_seconds = int(new_position)
                
                # Stop current playback
                mixer.music.stop()
                
                # Reload and play from the new position
                mixer.music.load(current_file)
                mixer.music.play(start=position_seconds)
                
                # Update the position
                current_position = new_position
                progress_var.set(new_position)
                current_time_label.config(text=format_time(new_position))
                
                # Resume progress updates
                if is_playing:
                    update_progress()
                    
            except Exception as e:
                print(f"Error seeking: {e}")
    
    def play_pause():
        nonlocal is_playing, current_position, paused_position
        try:
            if is_playing:
                mixer.music.pause()
                play_btn.config(image=play_img)
                play_btn.image = play_img
                is_playing = False
                if update_thread:
                    update_thread.cancel()
            else:
                if not mixer.music.get_busy():
                    if current_file and os.path.exists(current_file):
                        mixer.music.load(current_file)
                        current_position = paused_position
                        progress_var.set(current_position)
                        # Play from the paused position
                        mixer.music.play(start=int(paused_position))
                    else:
                        download_and_play(mp3_urls[current_track])
                else:
                    mixer.music.unpause()
                play_btn.config(image=pause_img)
                play_btn.image = pause_img
                is_playing = True
                update_progress()
        except Exception as e:
            print(f"Error in play/pause: {e}")
            is_playing = False
            play_btn.config(image=play_img)
            play_btn.image = play_img
    
    def next_track():
        nonlocal current_track, is_playing, paused_position
        if current_track < len(mp3_urls) - 1:
            current_track += 1
            is_playing = True
            paused_position = 0  # Reset paused position for new track
            play_btn.config(image=pause_img)
            play_btn.image = pause_img
            download_and_play(mp3_urls[current_track])
            
    def prev_track():
        nonlocal current_track, is_playing, paused_position
        if current_track > 0:
            current_track -= 1
            is_playing = True
            paused_position = 0  # Reset paused position for new track
            play_btn.config(image=pause_img)
            play_btn.image = pause_img
            download_and_play(mp3_urls[current_track])

    # Create main window
    root = tk.Tk()
    root.title("MP3 Miner")
    root.geometry("600x400")  # Made window larger for track list
    root.configure(bg='#f0f0f0')
    
    # Set icon if available
    app_icon = load_app_icon(root)
    if app_icon:
        root.iconphoto(True, app_icon)

    # Load control button images
    loaded_images = []  # Store references to prevent garbage collection
    def load_button_image(filename):
        try:
            if os.path.exists(filename):
                img = Image.open(filename).convert('RGBA')  # Force RGBA for transparency
                img = img.resize((48, 48), Image.Resampling.LANCZOS)
                tk_img = ImageTk.PhotoImage(img)
                loaded_images.append(tk_img)  # Prevent garbage collection
                print(f"Loaded image: {filename}")
                return tk_img
            else:
                print(f"File not found: {filename}")
        except Exception as e:
            print(f"Error loading {filename}: {e}")
        return None

    play_img = load_button_image('images/play.png')
    pause_img = load_button_image('images/pause.png')
    forward_img = load_button_image('images/forward.png')
    backward_img = load_button_image('images/backward.png')

    # Create main frame
    main_frame = ttk.Frame(root, padding="10")
    main_frame.pack(fill=tk.BOTH, expand=True)
    
    # Create left and right frames
    left_frame = ttk.Frame(main_frame)
    left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
    
    right_frame = ttk.Frame(main_frame)
    right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
    
    # Title label
    title_label = ttk.Label(right_frame, text="No track selected", font=('Helvetica', 12))
    title_label.pack(pady=10)
    
    # Track list
    list_frame = ttk.Frame(left_frame)
    list_frame.pack(fill=tk.BOTH, expand=True)
    
    ttk.Label(list_frame, text="Track List", font=('Helvetica', 10, 'bold')).pack(anchor=tk.W)
    
    # Create scrollbar
    scrollbar = ttk.Scrollbar(list_frame)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    # Create listbox
    track_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, 
                             selectmode=tk.SINGLE, font=('Helvetica', 10))
    track_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.config(command=track_listbox.yview)
    
    # Populate listbox
    for i, url in enumerate(mp3_urls):
        track_listbox.insert(tk.END, f"{i+1}. {get_track_name(url)}")
    
    # Bind double-click event
    track_listbox.bind('<Double-Button-1>', play_selected_track)
    
    # Progress bar and seeker
    progress_frame = ttk.Frame(right_frame)
    progress_frame.pack(fill=tk.X, pady=5)

    # Time labels
    current_time_label = ttk.Label(progress_frame, text="0:00", width=6, anchor='w')
    current_time_label.pack(side=tk.LEFT)

    progress_var = tk.DoubleVar()
    seeker = ttk.Scale(progress_frame, from_=0, to=100, orient=tk.HORIZONTAL,
                      variable=progress_var, length=220)
    seeker.pack(side=tk.LEFT, fill=tk.X, expand=True)

    total_time_label = ttk.Label(progress_frame, text="0:00", width=6, anchor='e')
    total_time_label.pack(side=tk.LEFT)
    
    # Bind seeker events
    seeker.bind("<ButtonPress-1>", on_seek_start)
    seeker.bind("<ButtonRelease-1>", on_seek_end)
    
    # Create buttons frame
    button_frame = ttk.Frame(right_frame)
    button_frame.pack(pady=10)
    
    # Create buttons with images using tk.Button for better image support
    btn_bg = '#f0f0f0'
    prev_btn = tk.Button(button_frame,
                        image=backward_img,
                        command=prev_track,
                        bd=0,
                        bg=btn_bg,
                        activebackground=btn_bg,
                        highlightthickness=0)
    prev_btn.image = backward_img
    prev_btn.pack(side=tk.LEFT, padx=10)

    play_btn = tk.Button(button_frame,
                        image=play_img,
                        command=play_pause,
                        bd=0,
                        bg=btn_bg,
                        activebackground=btn_bg,
                        highlightthickness=0)
    play_btn.image = play_img
    play_btn.pack(side=tk.LEFT, padx=10)

    next_btn = tk.Button(button_frame,
                        image=forward_img,
                        command=next_track,
                        bd=0,
                        bg=btn_bg,
                        activebackground=btn_bg,
                        highlightthickness=0)
    next_btn.image = forward_img
    next_btn.pack(side=tk.LEFT, padx=10)
    
    # Track counter
    track_counter = ttk.Label(right_frame, text=f"Track {current_track + 1} of {len(mp3_urls)}")
    track_counter.pack(pady=5)
    
    # Cleanup
    def cleanup():
        cleanup_current_file()
        mixer.quit()
        try:
            for file in os.listdir(temp_dir):
                try:
                    os.remove(os.path.join(temp_dir, file))
                except:
                    pass
            os.rmdir(temp_dir)
        except:
            pass
    
    # Bind cleanup to window close
    root.protocol("WM_DELETE_WINDOW", lambda: [cleanup(), root.destroy()])
    
    # Start UI
    root.mainloop()

def create_url_input_ui():
    """
    Creates a UI for URL input before showing the player
    """
    def on_submit():
        url = url_entry.get().strip()
        if not url:
            messagebox.showerror("Error", "Please enter a URL")
            return
            
        try:
            # Show loading state
            submit_btn.config(state='disabled')
            status_label.config(text="Searching for MP3 files...")
            root.update()
            
            # Get MP3 URLs
            mp3_urls = scrape_mp3_urls(url)
            
            if not mp3_urls:
                messagebox.showerror("Error", "No MP3 files found on the website")
                submit_btn.config(state='normal')
                status_label.config(text="")
                return
            
            # Add to history
            history = add_to_history(url)
            update_history_dropdown(history)
                
            # Close URL input window
            root.destroy()
            
            # Show player with found URLs
            create_player_ui(mp3_urls)
            
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred: {str(e)}")
            submit_btn.config(state='normal')
            status_label.config(text="")
    
    def on_history_select(event):
        selected = history_var.get()
        if selected:
            url_entry.delete(0, tk.END)
            url_entry.insert(0, selected)
    
    def update_history_dropdown(history):
        history_dropdown['values'] = [h['url'] for h in history]
        if history:
            history_dropdown.set(history[0]['url'])
    
    # Create main window
    root = tk.Tk()
    root.title("MP3 Scraper")
    root.geometry("500x250")  # Made window taller for history
    root.configure(bg='#f0f0f0')
    
    # Set icon if available
    app_icon = load_app_icon(root)
    if app_icon:
        root.iconphoto(True, app_icon)

    # Create main frame
    main_frame = ttk.Frame(root, padding="20")
    main_frame.pack(fill=tk.BOTH, expand=True)
    
    # History section
    history_frame = ttk.LabelFrame(main_frame, text="Recent Websites", padding="10")
    history_frame.pack(fill=tk.X, pady=(0, 10))
    
    # Load history
    history = load_url_history()
    history_var = tk.StringVar()
    
    # History dropdown
    history_dropdown = ttk.Combobox(history_frame, 
                                  textvariable=history_var,
                                  state='readonly',
                                  width=50)
    history_dropdown.pack(fill=tk.X)
    history_dropdown.bind('<<ComboboxSelected>>', on_history_select)
    
    # Update dropdown with history
    update_history_dropdown(history)
    
    # URL input label
    url_label = ttk.Label(main_frame, text="Enter website URL:", font=('Helvetica', 10))
    url_label.pack(anchor=tk.W, pady=(0, 5))
    
    # URL input field
    url_entry = ttk.Entry(main_frame, width=50, font=('Helvetica', 10))
    url_entry.pack(fill=tk.X, pady=(0, 10))
    url_entry.focus()  # Set focus to URL input
    
    # Submit button
    submit_btn = ttk.Button(main_frame, text="Search MP3 Files", command=on_submit)
    submit_btn.pack(pady=10)
    
    # Status label
    status_label = ttk.Label(main_frame, text="", font=('Helvetica', 9))
    status_label.pack(pady=5)
    
    # Bind Enter key to submit
    url_entry.bind('<Return>', lambda e: on_submit())
    
    # Start UI
    root.mainloop()

if __name__ == "__main__":
    # Start with URL input UI
    create_url_input_ui()
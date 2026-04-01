import flet as ft
import requests

# --- COLORS ---
DARK_GREY = "#121212"
BLACK = "#000000"
RED_MAGENTA = "#FF0055"
NEON_GREEN = "#00FF66"
WHITE = "#FFFFFF"
RED = "#FF0000"
# --- ENDPOINT ---
SERVER_URL = "https://4e62-178-209-155-47.ngrok-free.app/login"

def main(page: ft.Page):
    page.title = "Chat Client"
    page.bgcolor = DARK_GREY
    page.window.width = 1200
    page.window.height = 800
    page.theme_mode = ft.ThemeMode.DARK
    
    # CENTER THE CONTENT
    page.vertical_alignment = ft.MainAxisAlignment.CENTER
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER

    # Input Field
    name_input = ft.TextField(
        label="Enter your name",
        color=WHITE,
        border_color=RED_MAGENTA,
        width=300
    )

    # --- On Button Click ---
    def switch_ui(e):
        # Get the name from input
        user_name = name_input.value
        if not user_name:
            user_name = "Unknown User"

        # screen clear
        page.controls.clear()
        page.add(ft.ProgressRing(color=NEON_GREEN))
        page.update()

        # Request to my server
        try:
            response = requests.post(SERVER_URL, json={"name": user_name})
            data = response.json()
            
            # Grab whoami
            server_user = data.get("server_user", "Unknown Server")
            result_text = f"Hello World from {server_user}"
            text_color = NEON_GREEN

        except Exception as ex:
            # Down handle
            result_text = f"Connection failed! Is ngrok running?"
            text_color = RED

        # Draw result
        page.controls.clear()
        hello_box = ft.Container(
            content=ft.Text(result_text, size=40, color=text_color),
            border=ft.border.all(3, RED_MAGENTA),
            padding=30,
            border_radius=10
        )
        page.add(hello_box)
        page.update()

    # --- 1. Initial UI Setup ---
    # Login Button
    login_button = ft.ElevatedButton(
        "Login", 
        color=WHITE, 
        bgcolor=RED_MAGENTA, 
        on_click=switch_ui
    )

    # Adds buttons to the page
    page.add(name_input, login_button)

# RUN THE APP
ft.app(main)
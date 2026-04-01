import flet as ft

# --- COLORS ---
DARK_GREY = "#121212"
BLACK = "#000000"
RED_MAGENTA = "#FF0055"
NEON_GREEN = "#00FF66"
WHITE = "#FFFFFF"
RED = "#FF0000"

def main(page: ft.Page):
    page.title = "Chat Client"
    page.bgcolor = DARK_GREY
    page.window.width = 1200
    page.window.height = 800
    page.theme_mode = ft.ThemeMode.DARK
    
    # CENTER THE CONTENT
    page.vertical_alignment = ft.MainAxisAlignment.CENTER
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER

    # --- On Button Click ---
    def switch_ui(e):

        # screen clear
        page.controls.clear()
        
        # --- UI after "Login" ---
        hello_box = ft.Container(
            content=ft.Text("Hello World", size=40, color=NEON_GREEN),
            border=ft.border.all(3, RED_MAGENTA), 
            padding=30,                           
            border_radius=10                      
        )
        
        # Draw UI
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

    # Adds button to the page
    page.add(login_button)

# RUN THE APP
ft.app(main)
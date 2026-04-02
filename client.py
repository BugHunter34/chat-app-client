import flet as ft
import requests
import asyncio
import json
import websockets

# py
SERVER_IP = "9ced-178-209-155-47.ngrok-free.app" 
PORT = "8000"
API_URL = f"https://{SERVER_IP}"
WS_URL = f"wss://{SERVER_IP}/ws"

# Colors
DARK_GREY = "#121212"        # Dark grey
BLACK = "#000000"            # Black 
RED_MAGENTA = "#FF0055"      # Magenta/Red 
NEON_GREEN = "#00FF66"       # Neon green 
WHITE = "#FFFFFF"            # White 
RED = "#FF0000"              # Red

def main(page: ft.Page):
    page.title = "Chat Client"
    page.bgcolor = DARK_GREY
    page.window.width = 1200
    page.window.height = 800
    page.theme_mode = ft.ThemeMode.DARK 
    page.padding = 0

    # --- UI Components ---
    status_icon = ft.Icon(icon=ft.Icons.WIFI_OFF, size=50, color=RED)
    title = ft.Text("Connecting to server...", size=32, color=WHITE, weight=ft.FontWeight.W_800)
    
    email_field = ft.TextField(label="Email (For Register)", prefix_icon=ft.Icons.EMAIL, border_color=RED_MAGENTA)
    user_field = ft.TextField(label="Username", prefix_icon=ft.Icons.PERSON, border_color=RED_MAGENTA)
    pass_field = ft.TextField(label="Password", password=True, can_reveal_password=True, prefix_icon=ft.Icons.LOCK, border_color=RED_MAGENTA)
    
    snack_text = ft.Text("")
    page.snack_bar = ft.SnackBar(snack_text)

    is_connected = False

    # --- Auto-Ping ---
    async def auto_ping():
        nonlocal is_connected
        while not is_connected:
            try:
                response = requests.get(f"{API_URL}/ping", timeout=2)
                if response.status_code == 200:
                    status_icon.icon = ft.Icons.WIFI
                    status_icon.color = NEON_GREEN
                    title.value = "Connected! Please Login."
                    is_connected = True
                    page.update()
                    break
            except requests.exceptions.RequestException:
                pass # retry
            await asyncio.sleep(5)

    page.run_task(auto_ping)


    # ---Button Handlers ---
    def handle_register(e):
        if not email_field.value or not user_field.value or not pass_field.value:
            show_snack("Fill all fields!", RED)
            return
            
        payload = {"email": email_field.value, "userName": user_field.value, "password": pass_field.value}
        try:
            res = requests.post(f"{API_URL}/register", json=payload).json()
            if res.get("status") == "success":
                show_snack("Registered! You can now login.", NEON_GREEN)
            else:
                show_snack(res.get("detail", res.get("message")), RED)
        except Exception as ex:
            show_snack("Connection Error", RED)

    def handle_login(e):
        if not user_field.value or not pass_field.value:
            show_snack("Username and Password required!", RED)
            return

        payload = {"userName": user_field.value, "password": pass_field.value}
        try:
            res = requests.post(f"{API_URL}/login", json=payload).json()
            if res.get("status") == "success":
                # Pass data to UI
                build_chat_ui(
                    res.get("username"), 
                    res.get("friends", []), 
                    res.get("friendRequests", [])
                )
            else:
                show_snack(res.get("message"), RED)
        except Exception as ex:
            show_snack("Connection Error", RED)

    def show_snack(msg, color):
        snack_text.value = msg
        page.snack_bar.bgcolor = color
        page.snack_bar.open = True
        page.update()


    # --- Chat UI Builder ---
    def build_chat_ui(current_username, initial_friends, initial_requests):
        page.clean()
        page.horizontal_alignment = ft.CrossAxisAlignment.START
        page.vertical_alignment = ft.MainAxisAlignment.START

        # Vars
        active_chat = [None]  
        ws_connection = [None] 
        
        # Local memory to store history
        local_chat_history = {friend: [] for friend in initial_friends}

        # UI Containers
        pending_requests_list = ft.Column(spacing=5)
        user_list = ft.ListView(expand=True, spacing=10)
        chat_display = ft.ListView(expand=True, spacing=10, auto_scroll=True)
        chat_header = ft.Text("Select a friend to start chatting", size=20, color=RED_MAGENTA, weight="bold")

        # ---Func for the UI ---
        def set_active_chat(friend_name):
            active_chat[0] = friend_name
            chat_header.value = f"Chatting with {friend_name}"
            chat_display.controls.clear() # screen clear
            
            # does friend exist in memory?
            if friend_name not in local_chat_history:
                local_chat_history[friend_name] = []
                
            # Render memory
            for msg in local_chat_history[friend_name]:
                chat_display.controls.append(ft.Text(msg["text"], color=msg["color"]))
                
            page.update()

        def add_friend_to_ui(friend_name):
            if friend_name not in local_chat_history:
                local_chat_history[friend_name] = []
                
            tile = ft.ListTile(
                leading=ft.CircleAvatar(bgcolor=NEON_GREEN, content=ft.Icon(ft.Icons.PERSON, color="black")),
                title=ft.Text(friend_name, color=WHITE),
                subtitle=ft.Text("Offline", color=ft.Colors.WHITE54, size=12),
                on_click=lambda e: set_active_chat(friend_name) 
            )
            user_list.controls.append(tile)
            page.update()

        # render incoming friend requests
        def add_request_to_ui(requester):
            row = ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
            def respond(e, action):
                payload = {"requester": requester, "receiver": current_username, "action": action}
                requests.post(f"{API_URL}/respond-friend-request", json=payload, headers={"ngrok-skip-browser-warning": "true"})
                pending_requests_list.controls.remove(row)
                if action == "accept":
                    add_friend_to_ui(requester)
                    show_snack(f"You are now friends with {requester}!", NEON_GREEN)
                page.update()

            row.controls = [
                ft.Text(requester, color=NEON_GREEN, size=14, weight="bold"),
                ft.Row([
                    ft.IconButton(ft.Icons.CHECK, icon_color=NEON_GREEN, on_click=lambda e: respond(e, "accept")),
                    ft.IconButton(ft.Icons.CLOSE, icon_color=RED, on_click=lambda e: respond(e, "decline"))
                ], spacing=0)
            ]
            pending_requests_list.controls.append(row)
            page.update()

        # Load data from server
        for friend in initial_friends: add_friend_to_ui(friend)
        for req in initial_requests: add_request_to_ui(req)

        # --- THE WEBSOCKET TASK ---
        async def chat_websocket():
            uri = f"{WS_URL}/{current_username}"
            try:
                async with websockets.connect(uri, additional_headers={"ngrok-skip-browser-warning": "true"}) as websocket: # ngrok header to prevent browser
                    ws_connection[0] = websocket 
                    while True:
                        message = await websocket.recv()
                        data = json.loads(message)
                        
                        if data["type"] == "chat_message":
                            sender = data["from"]
                            msg_content = data["content"]
                            
                            if sender not in local_chat_history:
                                local_chat_history[sender] = []
                            
                            # Save to local memory
                            local_chat_history[sender].append({"text": f"{sender}: {msg_content}", "color": WHITE})
                            
                            # Update UI in active chat
                            if active_chat[0] == sender:
                                chat_display.controls.append(ft.Text(f"{sender}: {msg_content}", color=WHITE))
                                page.update()
                            else:
                                show_snack(f"New message from {sender}!", NEON_GREEN)
                                
                        elif data["type"] == "friend_request":
                            add_request_to_ui(data["from"])
                            
                        elif data["type"] == "friend_accepted":
                            add_friend_to_ui(data["friend"])
                            show_snack(f"{data['friend']} accepted your request!", NEON_GREEN)
                            
            except Exception as e:
                print(f"WebSocket Error: {e}")

        page.run_task(chat_websocket)

        # --- Friend Search ---
        friend_search_field = ft.TextField(label="Friend's Username", border_color=RED_MAGENTA, text_size=14, height=40)
        def send_friend_request(e):
            target = friend_search_field.value
            if not target or target == current_username: return
            res = requests.post(f"{API_URL}/friend-request", json={"from": current_username, "to": target}, headers={"ngrok-skip-browser-warning": "true"}).json()
            if res.get("status") == "success":
                show_snack(f"Request sent to {target}!", NEON_GREEN)
                friend_search_field.value = ""
            else:
                show_snack(res.get("message"), RED)
            page.update()
        # send request button
        add_friend_btn = ft.ElevatedButton("Send Request", on_click=send_friend_request, style=ft.ButtonStyle(color=WHITE, bgcolor=RED_MAGENTA))

        # --- Left Panel ---
        left_panel = ft.Container(
            width=250, border=ft.border.only(right=ft.BorderSide(2, RED_MAGENTA)), padding=10, 
            content=ft.Column([ft.Text("Friends", size=20, color=RED_MAGENTA, weight=ft.FontWeight.BOLD), user_list], expand=True) 
        )

        # --- Middle Panel - chat window ---
        chat_input = ft.TextField(expand=True, hint_text="Type a message...", border_color=RED_MAGENTA)
        
        async def send_msg_async(payload):
            if ws_connection[0]:
                await ws_connection[0].send(json.dumps(payload))

        def send_msg(e):
            if chat_input.value and active_chat[0]:
                msg_text = chat_input.value
                friend = active_chat[0]
                
                # Save to local memory
                local_chat_history[friend].append({"text": f"You: {msg_text}", "color": NEON_GREEN})
                
                # Draw on UI
                chat_display.controls.append(ft.Text(f"You: {msg_text}", color=NEON_GREEN))
                
                # Send to server via WebSocket
                payload = {"type": "chat_message", "to": friend, "content": msg_text}
                page.run_task(send_msg_async, payload)
                
                chat_input.value = ""
                page.update()
            elif not active_chat[0]:
                show_snack("Select a friend to chat with first!", RED)

        middle_panel = ft.Container(
            expand=True, padding=20,
            content=ft.Column([
                chat_header,
                ft.Container(content=chat_display, expand=True),
                ft.Row([chat_input, ft.IconButton(icon=ft.Icons.SEND, icon_color=RED_MAGENTA, on_click=send_msg)])
            ])
        )

        # --- Right Panel (Settings) ---
        right_panel = ft.Container(
            width=280, border=ft.border.only(left=ft.BorderSide(2, RED_MAGENTA)), padding=10, 
            content=ft.Column([
                ft.Text("Add Friend", size=16, color=WHITE),
                friend_search_field, add_friend_btn,
                ft.Divider(color=RED_MAGENTA),
                ft.Text("Pending Requests", size=16, color=WHITE),
                pending_requests_list 
            ], scroll=ft.ScrollMode.AUTO)
        )

        page.add(ft.Row([left_panel, middle_panel, right_panel], expand=True, spacing=0))
        page.update()

    # --- Login Layout ---
    login_btn = ft.Button("Login", on_click=handle_login, style=ft.ButtonStyle(bgcolor=RED_MAGENTA, color="white"))
    register_btn = ft.Button("Register", on_click=handle_register, style=ft.ButtonStyle(color=RED_MAGENTA))

    login_card = ft.Container(
        content=ft.Column([
            ft.Container(content=status_icon, alignment=ft.Alignment.CENTER),
            title,
            email_field, user_field, pass_field,
            ft.Row([login_btn, register_btn], alignment=ft.MainAxisAlignment.CENTER)
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        bgcolor=BLACK, padding=40, border_radius=20, width=450,
        border=ft.border.all(2, RED_MAGENTA)
    )

    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.vertical_alignment = ft.MainAxisAlignment.CENTER
    page.add(login_card)

ft.run(main)
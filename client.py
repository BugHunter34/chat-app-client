import flet as ft
import flet_audio as fta
import requests
import asyncio
import json
import time


# --- Cross Platform ---
try:
    # Web Mode (Pyodide)
    import js
    from pyodide.ffi import create_proxy
    IS_WEB = True
except ImportError:
    # Desktop Mode 
    import websockets
    IS_WEB = False

# --- Config - domain ---
SERVER_DOMAIN = "api.andhyy.com" 
API_URL = f"https://{SERVER_DOMAIN}"

# --- colors ---
DARK_GREY = "#121212"
BLACK = "#000000"
RED_MAGENTA = "#FF0055"
NEON_GREEN = "#00FF66"
WHITE = "#FFFFFF"
RED = "#FF0000"

EMOJI_MAP = {
    ":cry:": f"{API_URL}/emojis/cry-emoji.png",
    #":lol:": f"{API_URL}/emojis/lol.png",
    #":fire:": f"{API_URL}/emojis/fire.png"
}

def parse_message_to_ui(prefix_text, message_content, text_color):
    """
   split messages into text/emoji 
    """
    ui_controls = [ft.Text(f"{prefix_text}: ", color=text_color, weight="bold")]

    # if it starts with IMG it will render bigger instead of text/emoji
    if message_content.startswith("[IMG]"):
        img_url = message_content.replace("[IMG]", "").strip() 
        ui_controls.append(ft.Image(src=img_url, width=250, height=250, border_radius=10, fit=ft.BoxFit.CONTAIN))
        return ft.Row(controls=ui_controls, vertical_alignment=ft.CrossAxisAlignment.START)
    
    # split to check for codes
    words = message_content.split()
    
    current_text = ""
    for word in words:
        if word in EMOJI_MAP:
            if current_text:
                ui_controls.append(ft.Text(current_text, color=text_color))
                current_text = "" # Reset
            
            # add the tiny emoji
            ui_controls.append(ft.Image(src=EMOJI_MAP[word], width=24, height=24))
        else:
            # the rest of text
            current_text += word + " "
            
    # remaining text
    if current_text:
        ui_controls.append(ft.Text(current_text, color=text_color))
         
    # if too long go to next line
    return ft.Row(controls=ui_controls, spacing=2, wrap=True)

def main(page: ft.Page):
    page.title = "Andhyy Chat"
    page.bgcolor = DARK_GREY
    page.window.width = 1200
    page.window.height = 800
    page.theme_mode = ft.ThemeMode.DARK 
    page.padding = 0

    # mp3 notifs paths
    WB_sound = fta.Audio(src=f"{API_URL}/sounds/welcome.mp3", autoplay=False)
    ping_sound = fta.Audio(src=f"{API_URL}/sounds/notif.mp3", volume=300.0, autoplay=False)
    error_sound = fta.Audio(src=f"{API_URL}/sounds/error.mp3", autoplay=False)

    def handle_notif_sound():
        show_snack("playing", NEON_GREEN)
        try:
            ping_sound.seek(0) # reset audio to start
            page.run_task(ping_sound.play)  
            page.run_task(ping_sound.play)  # played twice since it doesn't want to play for the first time
            show_snack("played", NEON_GREEN)
        except Exception as e:
            show_snack(f"Failed to play sound: {e}", RED)
            ping_sound.seek(0)
            page.run_task(error_sound.play)
            page.run_task(error_sound.play)

    # the sound notifs
    page.services.append(ping_sound)
    page.services.append(error_sound)
    page.services.append(WB_sound)
    page.update()

    # --- UI for login ---
    status_icon = ft.Icon(icon=ft.Icons.WIFI_OFF, size=50, color=RED)
    title = ft.Text("Connecting to server...", size=32, color=WHITE, weight=ft.FontWeight.W_800)
    
    email_field = ft.TextField(label="Email (For Register)", prefix_icon=ft.Icons.EMAIL, border_color=RED_MAGENTA)
    user_field = ft.TextField(label="Username", prefix_icon=ft.Icons.PERSON, border_color=RED_MAGENTA)
    pass_field = ft.TextField(label="Password", password=True, can_reveal_password=True, prefix_icon=ft.Icons.LOCK, border_color=RED_MAGENTA)
    
    snack_text = ft.Text("")
    page.snack_bar = ft.SnackBar(content=snack_text)

    is_connected = False

    # --- Ping ---
    async def auto_ping():
        nonlocal is_connected
        while not is_connected:
            try:
                response = requests.get(f"{API_URL}/ping", timeout=3)
                if response.status_code == 200:
                    try:
                        data = response.json() 
                        status_icon.icon = ft.Icons.WIFI
                        status_icon.color = NEON_GREEN
                        title.value = "Connected! Please Login."
                        is_connected = True
                        page.update()
                        break
                    except ValueError:
                        title.value = "Proxy error, Retrying..."
                        page.update()
                else:
                    title.value = f"Server Offline ({response.status_code}). Retrying..."
                    page.update()

            except requests.exceptions.RequestException:
                title.value = "Server Offline. Retrying..."
                status_icon.icon = ft.Icons.WIFI_OFF
                status_icon.color = RED
                page.update()
                
            await asyncio.sleep(5)

    page.run_task(auto_ping)

    # --- Handlers ---
    # erorr popup
    def show_snack(msg, color):
        snack = ft.SnackBar(content=ft.Text(msg, color=BLACK, weight="bold"), bgcolor=color)
        page.overlay.append(snack)
        snack.open = True
        page.update()

    def handle_register(e):
        if not email_field.value or not user_field.value or not pass_field.value:
            show_snack("some Field is missing", RED)
            return
            
        payload = {"email": email_field.value, "userName": user_field.value, "password": pass_field.value}
        try:
            response = requests.post(f"{API_URL}/register", json=payload, timeout=5)
            try:
                res = response.json()
            except ValueError:
                show_snack("Couldn't reach server (Proxy eror).", RED)
                return

            if res.get("status") == "success":
                show_snack("Register success, please log in", NEON_GREEN)
            else:
                show_snack(res.get("detail", res.get("message", "Registration failed")), RED)
                
        except requests.exceptions.RequestException:
            show_snack("Couldn't reach server.", RED)

    def handle_login(e):
        if not user_field.value or not pass_field.value:
            show_snack("Username and Password required!", RED)
            return

        payload = {"userName": user_field.value, "password": pass_field.value}
        try:
            response = requests.post(f"{API_URL}/login", json=payload, timeout=5)
            try:
                res = response.json()
            except ValueError:
                show_snack("Couldn't reach server (Proxy error)", RED)
                return

            if res.get("status") == "success":
                # save token if accepted cookies
                async def save_token():
                    if await prefs.get("cookies_accepted"):
                        await prefs.set("auth_token", res.get("token"))
                page.run_task(save_token)

                build_chat_ui(
                    res.get("username", user_field.value), 
                    res.get("role", "user"),
                    res.get("friends", []), 
                    res.get("friendRequests", [])
                )
            else:
                show_snack(res.get("message", "Invalid login details"), RED)
                
        except requests.exceptions.RequestException:
            show_snack("Couldn't reach server.", RED)

    # --- UI builder ---
    def build_chat_ui(current_username, role, initial_friends, initial_requests):
        page.clean()
        page.horizontal_alignment = ft.CrossAxisAlignment.START
        page.vertical_alignment = ft.MainAxisAlignment.START

        app_state = {
            "active_chat": None,
            "ws_connection": None,
            "role": role,
            "local_chat_history": {friend: [] for friend in initial_friends}
        }
        app_state["last_typing_time"] = 0
        pending_requests_list = ft.Column(spacing=5, controls=[])
        user_list = ft.ListView(expand=True, spacing=10, controls=[])
        chat_display = ft.ListView(expand=True, spacing=10, auto_scroll=True, controls=[])
        typing_indicator = ft.Text("", color=ft.Colors.WHITE54, size=12, italic=True)
        chat_header = ft.Text("select friend to chat", size=20, color=RED_MAGENTA, weight="bold")

        def refresh_chat_display():
            chat_display.controls.clear()
            friend_name = app_state["active_chat"]
            
            if friend_name and friend_name in app_state["local_chat_history"]:
                for msg_data in app_state["local_chat_history"][friend_name]:
                    
                    sender = msg_data["sender"]
                    content = msg_data["content"]
                    
                    # color based on sender
                    color = NEON_GREEN if sender == current_username else WHITE
                    prefix = "You" if sender == current_username else sender
                    
                    # build the emoji/text 
                    bubble = parse_message_to_ui(prefix, content, color)
                    chat_display.controls.append(bubble)
                    
            page.update()

        def set_active_chat(friend_name):
            app_state["active_chat"] = friend_name
            chat_header.value = f"Chatting with {friend_name}"

            # remove notif when clicked on user
            for tile in user_list.controls:
                if tile.title.value == friend_name:
                    tile.trailing.visible = False
                    page.update()
                    break
            # Fetch history from DB
            try:
                res = requests.get(f"{API_URL}/messages", params={"user1": current_username, "user2": friend_name}).json()
                if res.get("status") == "success":
                    # clear so it doesnt duplicate
                    app_state["local_chat_history"][friend_name] = []
                    
                    for msg in res["messages"]:
                        # save to local history
                        app_state["local_chat_history"][friend_name].append({
                            "sender": msg["sender"], 
                            "content": msg["content"]
                        })
            except Exception as e:
                show_snack("Couldn't load chat history", RED)

            refresh_chat_display()

        def check_active_user(friend_name):
            payload = {"userName": friend_name}
            try: 
                response = requests.get(f"{API_URL}/user-status", params=payload, timeout=5)
                try:
                    res = response.json()
                    if res.get("status") == "online":
                        return "Online"
                    else:                        
                        return "Offline"
                except ValueError:
                    return "error"
            except requests.exceptions.RequestException:
                show_snack("Couldn't check user status.", RED)
                return False
            
        def add_friend_to_ui(friend_name):
            if friend_name not in app_state["local_chat_history"]:
                app_state["local_chat_history"][friend_name] = []
            
            notification_badge = ft.Container(
                content=ft.Text("New", size=10, color=WHITE, weight="bold"),
                bgcolor=RED,
                padding=ft.padding.only(left=6, right=6, top=2, bottom=2),
                border_radius=10,
                visible=False # hide by deafult
                
            )

            tile = ft.ListTile(
                leading=ft.CircleAvatar(bgcolor=NEON_GREEN, content=ft.Icon(ft.Icons.PERSON, color=BLACK)),
                title=ft.Text(friend_name, color=WHITE),
                subtitle=ft.Text(check_active_user(friend_name), color=ft.Colors.WHITE54, size=12),
                trailing=notification_badge, #notif
                on_click=lambda e, name=friend_name: set_active_chat(name) 
            )
            user_list.controls.append(tile)
            page.update()

        def add_request_to_ui(requester):
            async def respond(e, action):
                payload = {"requester": requester, "receiver": current_username, "action": action}
                res = requests.post(f"{API_URL}/respond-friend-request", json=payload)
                if res.status_code == 200:
                    pending_requests_list.controls.remove(request_row)
                    if action == "accept":
                        add_friend_to_ui(requester)
                        show_snack(f"New friend: {requester}!", NEON_GREEN)
                        ping_sound.play()
                    page.update()

            request_row = ft.Row(
                controls=[
                    ft.Text(requester, color=NEON_GREEN, size=14, weight="bold"),
                    ft.Row(
                        controls=[
                            ft.IconButton(ft.Icons.CHECK, icon_color=NEON_GREEN, on_click=lambda e: page.run_task(respond, e, "accept")),
                            ft.IconButton(ft.Icons.CLOSE, icon_color=RED, on_click=lambda e: page.run_task(respond, e, "decline"))
                        ], 
                        spacing=0
                    )
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN
            )
            pending_requests_list.controls.append(request_row)
            page.update()

        for friend in initial_friends: add_friend_to_ui(friend)
        for req in initial_requests: add_request_to_ui(req)

        # --- CROSS-PLATFORM WEBSOCKET LOGIC ---
        # coulnd't use websocket lib in web since "ssl" error so diff libs for web / desktop
        def process_incoming_message(data):
            try:
                if isinstance(data, dict) and data.get("type") == "chat_message":
                    sender = data.get("from") or data.get("sender")
                    content = data.get("content")


                    if sender not in app_state["local_chat_history"]:
                        app_state["local_chat_history"][sender] = []
                    
                    # save raw
                    app_state["local_chat_history"][sender].append({"sender": sender, "content": content})


                    if app_state["active_chat"] == sender:
                        # draw emoji/text 
                        bubble = parse_message_to_ui(sender, content, WHITE)
                        chat_display.controls.append(bubble)
                        chat_display.update()
                    else:
                        handle_notif_sound()
                        show_snack(f"New message from {sender}", NEON_GREEN)
                        
                        # show notif
                        for tile in user_list.controls:
                            if tile.title.value == sender:
                                tile.trailing.visible = True
                                tile.update()
                                break
                        
                        

                # typing indicator
                elif isinstance(data, dict) and data.get("type") == "typing":
                    sender = data.get("from")
                    if app_state["active_chat"] == sender:
                        typing_indicator.value = f"{sender} is typing..."
                        typing_indicator.update()
                        
                        # clear after 3s
                        async def clear_typing():
                            await asyncio.sleep(3)
                            typing_indicator.value = ""
                            typing_indicator.update()
                        page.run_task(clear_typing)

                elif isinstance(data, dict) and data.get("type") == "friend_request":
                    requester_name = data.get("from") or data.get("requester")
                    if requester_name:
                        add_request_to_ui(requester_name)
                        handle_notif_sound()
                        show_snack(f"New friend request from {requester_name}!", NEON_GREEN)
                    
                elif isinstance(data, dict) and data.get("type") == "friend_accepted":
                    add_friend_to_ui(data.get("friend"))
                    handle_notif_sound()
                    show_snack(f"{data.get('friend')} accepted your request!", NEON_GREEN)
                
                # realtime status update between online/offline
                elif isinstance(data, dict) and data.get("type") == "status_update":
                    target_user = data.get("username")
                    new_status = data.get("status") 
                    
                    if target_user:
                        # loop trought users
                        for tile in user_list.controls:
                            # case insens match
                            if tile.title.value.lower() == target_user.lower():
                                tile.subtitle.value = new_status.capitalize()
                                tile.update()
                                break

            except Exception as ex:
                print(f"Message parse error: {ex}")

                
        if IS_WEB:
            # WEB MODE (Pyodide)
            async def on_ws_message(event):
                process_incoming_message(json.loads(event.data))

            def on_ws_disconnect(event):
                show_snack("WebSocket Disconnected.", RED)
                page.update()

            ws = js.WebSocket.new(f"wss://{SERVER_DOMAIN}/ws/{current_username}")
            ws.onmessage = create_proxy(on_ws_message)
            ws.onclose = create_proxy(on_ws_disconnect)
            
            app_state["ws_connection"] = ws 
        else:
            # VSC / Desktop  (Standard Python connection)
            async def desktop_ws():
                WS_URL = f"wss://{SERVER_DOMAIN}/ws/{current_username}"
                try:
                    async with websockets.connect(WS_URL) as websocket:
                        app_state["ws_connection"] = websocket 
                        while True:
                            msg_raw = await websocket.recv()
                            process_incoming_message(json.loads(msg_raw))
                except Exception as e:
                    print(f"WS Connection Error: {e}")
                    show_snack("Lost connection, restart required ig", RED)

            page.run_task(desktop_ws)

        # --- Friend Search ---
        friend_search_field = ft.TextField(label="Find User", border_color=RED_MAGENTA, height=45)
        def send_friend_request(e):
            target = friend_search_field.value
            if not target or target == current_username: return
            res = requests.post(f"{API_URL}/friend-request", json={"from": current_username, "to": target}).json()
            if res.get("status") == "success":
                show_snack(f"Sent to {target}!", NEON_GREEN)
                friend_search_field.value = ""
            else:
                show_snack(res.get("message"), RED)
            page.update()

        # --- File Uploader---
        async def on_image_picked(e):
            # call the service
            files = await ft.FilePicker().pick_files(allow_multiple=False)
            
            # picked and confirmed
            if files and app_state["active_chat"]:
                friend = app_state["active_chat"]
                filepath = files[0].path
                
                show_snack("Uploading image...", ft.Colors.BLUE)
                
                try:
                    # Upload to FastAPI
                    with open(filepath, "rb") as f:
                        res = requests.post(f"{API_URL}/upload", files={"file": f}).json()
                    
                    if res.get("status") == "success":
                        img_url = res["url"]
                        msg_text = f"[IMG]{img_url}"
                        
                        # Save to history and render
                        app_state["local_chat_history"][friend].append({"sender": current_username, "content": msg_text})
                        bubble = parse_message_to_ui("You", msg_text, NEON_GREEN)
                        chat_display.controls.append(bubble)
                        page.update()
                        
                        # Broadcast via WebSocket
                        payload = {"type": "chat_message", "to": friend, "content": msg_text}
                        if IS_WEB:
                            if app_state["ws_connection"]:
                                app_state["ws_connection"].send(json.dumps(payload))
                        else:
                            async def transmit():
                                if app_state["ws_connection"]:
                                    await app_state["ws_connection"].send(json.dumps(payload))
                            page.run_task(transmit)
                            
                    else:
                        show_snack(res.get("message"), RED)
                except Exception as ex:
                    show_snack(f"Failed to upload image: {ex}", RED)
        

        def handle_typing_change(e):
            # Only send a ping every 2 seconds
            if time.time() - app_state["last_typing_time"] > 2 and app_state["active_chat"]:
                app_state["last_typing_time"] = time.time()
                
                payload = {"type": "typing", "to": app_state["active_chat"], "from": current_username}
                if IS_WEB:
                    if app_state["ws_connection"]:
                        app_state["ws_connection"].send(json.dumps(payload))
                else:
                    async def transmit():
                        if app_state["ws_connection"]:
                            await app_state["ws_connection"].send(json.dumps(payload))
                    page.run_task(transmit)
        # --- Update Chat Input---
        chat_input = ft.TextField(expand=True, hint_text="Message...", border_color=RED_MAGENTA, on_submit=lambda e: send_msg(e),on_change=handle_typing_change)
        send_btn = ft.IconButton(icon=ft.Icons.SEND, icon_color=NEON_GREEN, on_click=lambda e: send_msg(e))
        attach_btn = ft.IconButton(icon=ft.Icons.IMAGE, icon_color=WHITE, on_click=on_image_picked)
        chat_input_row = ft.Row(controls=[attach_btn, chat_input, send_btn])


        def send_msg(e):
            if chat_input.value and app_state["active_chat"]:
                msg_text = chat_input.value
                friend = app_state["active_chat"]
                
                app_state["local_chat_history"][friend].append({"text": f"You: {msg_text}", "color": NEON_GREEN})
                chat_display.controls.append(ft.Text(f"You: {msg_text}", color=NEON_GREEN))
                
                payload = {"type": "chat_message", "to": friend, "content": msg_text}
                
                if IS_WEB:
                    if app_state["ws_connection"]:
                        app_state["ws_connection"].send(json.dumps(payload))
                else:
                    async def transmit():
                        if app_state["ws_connection"]:
                            await app_state["ws_connection"].send(json.dumps(payload))
                    page.run_task(transmit)
                
                chat_input.value = ""
                page.update()

        # --- Final Layout -prototype ---

        # standart add friend view
        add_friend_view = ft.Column(
            controls=[
                ft.Text("Add Friend", color=WHITE, weight="bold"),
                friend_search_field,
                ft.ElevatedButton("Send Request", on_click=send_friend_request, bgcolor=RED_MAGENTA, color=WHITE),
                ft.Divider(color=ft.Colors.WHITE24),
                ft.Text("Pending", color=WHITE, weight="bold"),
                pending_requests_list
            ], 
            scroll=ft.ScrollMode.AUTO,
            expand=True
        )

        # The Admin view 
        all_users_list_ui = ft.ListView(expand=True, spacing=10, auto_scroll=True, controls=[], width=300)
        admin_view = ft.Column(
            controls=[
                ft.Text("Database Users", color=RED, weight="bold", size=18),
                all_users_list_ui,
                ft.ElevatedButton("Back", on_click=lambda e: toggle_admin_view(False), bgcolor=DARK_GREY, color=WHITE)
            ],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            horizontal_alignment=ft.CrossAxisAlignment.START
        )

        # outside container to switch between user/admin mode
        right_sidebar_content = ft.Container(content=add_friend_view, expand=True)

        def toggle_admin_view(show_admin):
                if show_admin:
                    right_sidebar_content.content = admin_view
                    all_users_list_ui.controls.clear()
                    
                    # Fetch all users frombackend
                    try:
                        res = requests.get(f"{API_URL}/all-users", params={"requester_role": app_state["role"]}).json()
                        
                        if res.get("status") == "success":
                            for user in res["users"]:
                                username = user["userName"] or user.get("username") or "Unknown"
                                role = user.get("role", "user")
                                status = user.get("status", "offline")
                                
                                # won't show OP button to admin users
                                op_button = ft.Container()
                                if role != "admin":
                                    op_button = ft.IconButton(
                                        icon=ft.Icons.STAR, 
                                        icon_color=ft.Colors.AMBER, 
                                        tooltip="OP this user",
                                        on_click=lambda e, target=username: promote_to_admin(target)
                                    )

                                user_row = ft.ListTile(
                                    leading=ft.Icon(ft.Icons.PERSON, color=NEON_GREEN if status == "online" else ft.Colors.GREY),
                                    title=ft.Text(f"{username} ({role})", color=WHITE, no_wrap=True),
                                    subtitle=ft.Text(user.get("email"), color=ft.Colors.WHITE54, size=12, no_wrap=True),
                                    trailing=op_button
                                )
                                all_users_list_ui.controls.append(user_row)
                                
                    except Exception as e:
                        show_snack("Failed to load users", RED)
                        
                else:
                    right_sidebar_content.content = add_friend_view
                
                page.update()

        # triggered by star button
        def promote_to_admin(target_username):
            payload = {"requester": current_username, "target": target_username}
            try:
                res = requests.post(f"{API_URL}/promote", json=payload).json()
                if res.get("status") == "success":
                    show_snack(res.get("message"), NEON_GREEN)
                    # Refresh
                    toggle_admin_view(True) 
                else:
                    show_snack(res.get("message"), RED)
            except Exception as e:
                show_snack("Failed to connect to server", RED)

        # switch
        if app_state.get("role") == "admin":
            add_friend_view.controls.insert(0, ft.ElevatedButton(
                "show all users", 
                bgcolor=RED, 
                color=WHITE, 
                on_click=lambda e: toggle_admin_view(True)
            ))
        
        # Desktop UI 
        left_column = ft.Container(
            col={"xs": 12, "md": 3, "lg": 2, "xl": 2},
            expand=True,
            padding=10,
            border=ft.border.all(1, RED_MAGENTA),
            content=ft.Column([ft.Text("Friends List", color=WHITE, weight="bold"), user_list])
        )

        center_column = ft.Container(
            col={"xs": 12, "md": 6, "lg": 7, "xl": 8},
            expand=True,
            padding=10,
            border=ft.border.all(1, RED_MAGENTA),
            content=ft.Column([chat_header, chat_display, chat_input_row]) 
        )

        right_column = ft.Container(
            col={"xs": 12, "md": 3, "lg": 3, "xl": 2},
            width=320,
            expand=True,
            padding=10,
            border=ft.border.all(1, RED_MAGENTA),
            content=right_sidebar_content 
        )

        # --- Mobile UI ---
        mobile_drawer = ft.NavigationDrawer(
            controls=[
                ft.Container(padding=20, content=ft.Text("Friends List", color=RED_MAGENTA, size=20, weight="bold")),
            ],
            bgcolor=DARK_GREY
        )
        page.drawer = mobile_drawer

        mobile_appbar = ft.AppBar(
            leading=ft.IconButton(ft.Icons.MENU, icon_color=NEON_GREEN, on_click=lambda e: page.open(mobile_drawer)),
            title=ft.Text("Andhyy Chat", color=WHITE, weight="bold"),
            bgcolor=BLACK,
            actions=[
                ft.IconButton(ft.Icons.PERSON_ADD, icon_color=RED_MAGENTA, on_click=lambda e: page.open(
                    # wrap so flet doesn't cry
                    ft.BottomSheet(ft.Container(padding=20, bgcolor=DARK_GREY, content=ft.Column([
                        ft.Text("Swipe down to close", color=ft.Colors.WHITE54),
                        right_sidebar_content
                    ])))
                ))
            ]
        )

        # ---Responsive Resize Handler ---
        def handle_resize(e):
            is_mobile = page.width < 800 
            
            #hide desktop sidebars
            left_column.visible = not is_mobile
            right_column.visible = not is_mobile
            
            # Prevent Flet Crash - moved user list
            if is_mobile:
                if user_list in left_column.content.controls:
                    left_column.content.controls.remove(user_list)
                if user_list not in mobile_drawer.controls:
                    mobile_drawer.controls.append(user_list)
            else:
                if user_list in mobile_drawer.controls:
                    mobile_drawer.controls.remove(user_list)
                if user_list not in left_column.content.controls:
                    left_column.content.controls.append(user_list)
            
            # only show it on mobile
            page.appbar = mobile_appbar if is_mobile else None
            page.update()

        page.on_resize = handle_resize

        # ---Add to Page ---
        page.add(
            ft.ResponsiveRow(
                controls=[left_column, center_column, right_column], 
                expand=True
            )
        )
        
        # resize trigger 
        handle_resize(None)

    # --- Login/register Screen ---
    login_btn = ft.ElevatedButton("Login", on_click=handle_login, style=ft.ButtonStyle(bgcolor=RED_MAGENTA, color=WHITE))
    register_btn = ft.TextButton("Register", on_click=handle_register, style=ft.ButtonStyle(color=RED_MAGENTA))

    login_card = ft.Container(
        content=ft.Column(
            controls=[
                status_icon,
                title,
                email_field,
                user_field,
                pass_field,
                login_btn,
                register_btn
            ], 
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER
        ),
        bgcolor=BLACK, 
        padding=40, 
        border_radius=20, 
        width=450,
        border=ft.border.all(2, RED_MAGENTA)
    )

    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.vertical_alignment = ft.MainAxisAlignment.CENTER

    # --- Cookie auto login ---
    prefs = ft.SharedPreferences()

    def show_cookie_banner():
        def accept_cookies(e):
            # Save cookie async
            page.run_task(prefs.set, "cookies_accepted", True)
            cookie_banner.open = False
            page.update()

        cookie_banner = ft.BottomSheet(
            ft.Container(
                padding=20,
                bgcolor=DARK_GREY,
                content=ft.Column([
                    ft.Text("our cookies keep you logged in for 24h", color=WHITE),
                    ft.ElevatedButton("Accept", on_click=accept_cookies, bgcolor=NEON_GREEN, color=BLACK)
                ], tight=True)
            )
        )
        page.overlay.append(cookie_banner)
        cookie_banner.open = True
        page.update()

    # async to check token while app is loading
    async def boot_app():
        saved_token = await prefs.get("auth_token")
        
        if saved_token:
            try:
                res = requests.get(f"{API_URL}/verify-token", params={"token": saved_token}, timeout=5).json()
                if res.get("status") == "success":
                    # this will unlock audio on web since browser can't play mp3 until user interacts with the app
                    def unlock_audio_and_enter(e):
                        # play nothing - just so it can work
                        WB_sound.play()

                        # Build the UI
                        build_chat_ui(
                            res.get("username"), 
                            res.get("role", "user"), 
                            res.get("friends", []), 
                            res.get("friendRequests", [])
                        )

                    # WB screen
                    page.clean()
                    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
                    page.vertical_alignment = ft.MainAxisAlignment.CENTER
                    page.add(
                        ft.Column(
                            controls=[
                                ft.Icon(ft.Icons.CHECK_CIRCLE, color=NEON_GREEN, size=60),
                                ft.Text(f"Welcome back, {res.get('username')}!", size=24, color=WHITE, weight="bold"),
                                ft.ElevatedButton(
                                    "Enter Chat", 
                                    bgcolor=RED_MAGENTA, 
                                    color=WHITE, 
                                    on_click=unlock_audio_and_enter # unlock
                                )
                            ],
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER
                        )
                    )
                    return # exit
            except Exception:
                await prefs.remove("auth_token")

        # if invalid show login
        page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
        page.vertical_alignment = ft.MainAxisAlignment.CENTER
        page.add(login_card)

        # check if accepted
        cookies_accepted = await prefs.get("cookies_accepted")
        if not cookies_accepted:
            show_cookie_banner()

    # run the boot
    page.run_task(boot_app)

ft.run(main)
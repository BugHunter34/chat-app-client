import flet as ft
import requests
import asyncio
import json

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

# --- Colors ---
DARK_GREY = "#121212"
BLACK = "#000000"
RED_MAGENTA = "#FF0055"
NEON_GREEN = "#00FF66"
WHITE = "#FFFFFF"
RED = "#FF0000"

def main(page: ft.Page):
    page.title = "Andhyy Chat"
    page.bgcolor = DARK_GREY
    page.window.width = 1200
    page.window.height = 800
    page.theme_mode = ft.ThemeMode.DARK 
    page.padding = 0

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
        snack = ft.SnackBar(content=ft.Text(msg, color=WHITE), bgcolor=color)
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

        pending_requests_list = ft.Column(spacing=5, controls=[])
        user_list = ft.ListView(expand=True, spacing=10, controls=[])
        chat_display = ft.ListView(expand=True, spacing=10, auto_scroll=True, controls=[])
        chat_header = ft.Text("select friend to chat", size=20, color=RED_MAGENTA, weight="bold")

        def refresh_chat_display():
            chat_display.controls.clear()
            friend_name = app_state["active_chat"]
            if friend_name and friend_name in app_state["local_chat_history"]:
                for msg_data in app_state["local_chat_history"][friend_name]:
                    chat_display.controls.append(ft.Text(msg_data["text"], color=msg_data["color"]))
            page.update()

        def set_active_chat(friend_name):
            app_state["active_chat"] = friend_name
            chat_header.value = f"Chatting with {friend_name}"
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
            tile = ft.ListTile(
                leading=ft.CircleAvatar(bgcolor=NEON_GREEN, content=ft.Icon(ft.Icons.PERSON, color=BLACK)),
                title=ft.Text(friend_name, color=WHITE),
                subtitle=ft.Text(check_active_user(friend_name), color=ft.Colors.WHITE54, size=12),
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
                    
                    app_state["local_chat_history"][sender].append({"text": f"{sender}: {content}", "color": WHITE})
                    
                    if app_state["active_chat"] == sender:
                        chat_display.controls.append(ft.Text(f"{sender}: {content}", color=WHITE))
                        page.update()
                    else:
                        show_snack(f"New message from {sender}", NEON_GREEN)
                        
                elif isinstance(data, dict) and data.get("type") == "friend_request":
                    requester_name = data.get("from") or data.get("requester")
                    if requester_name:
                        add_request_to_ui(requester_name)
                        show_snack(f"New friend request from {requester_name}!", NEON_GREEN)
                    
                elif isinstance(data, dict) and data.get("type") == "friend_accepted":
                    add_friend_to_ui(data.get("friend"))
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
                                page.update()
                                break

            except Exception as ex:
                print(f"Message parse error: {ex}")

                
        if IS_WEB:
            # WEB MODE (Pyodide)
            def on_ws_message(event):
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

        # --- Chat Input handle ---
        chat_input = ft.TextField(expand=True, hint_text="Message...", border_color=RED_MAGENTA, on_submit=lambda e: send_msg(e))
        send_btn = ft.IconButton(icon=ft.Icons.SEND, icon_color=NEON_GREEN, on_click=lambda e: send_msg(e))
        chat_input_row = ft.Row(controls=[chat_input, send_btn])

        def send_msg(e):
            if chat_input_row.value and app_state["active_chat"]:
                msg_text = chat_input_row.value
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
    page.add(login_card)

ft.run(main)
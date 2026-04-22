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

# ---- parses text messages to inject emojis or images ----
def parse_message_to_ui(prefix_text, message_content, text_color):
    #split messages into text/emoji 
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

# ---- info/error popup ----
def show_snack(page: ft.Page, msg: str, color: str):
    snack = ft.SnackBar(
        content=ft.Text(msg, color=BLACK, weight="bold"), 
        bgcolor=color,
        behavior=ft.SnackBarBehavior.FLOATING, # will float
        duration=2700
    )
    page.overlay.append(snack)
    snack.open = True
    page.update()


# ---- file uploader ----
async def upload_to_server(f: ft.FilePickerFile, API_URL: str, is_web: bool, file_picker: ft.FilePicker, sender: str, receiver: str = None):
    try:
        if is_web:
            upload_url = f"{API_URL}/upload?sender={sender}"
            if receiver:
                upload_url += f"&receiver={receiver}"
                
            upload_list = [ft.FilePickerUploadFile(name=f.name, upload_url=upload_url, method="POST")]
            await file_picker.upload(upload_list)
            return {"status": "success", "url": f"{API_URL}/images/{f.name}"}

        else:
            with open(f.path, "rb") as file_data:
                upload_url = f"{API_URL}/upload?sender={sender}"
                if receiver:
                    upload_url += f"&receiver={receiver}"
                    
                res = requests.post(upload_url, files={"file": file_data}).json()
                return res
    except Exception as ex:
        return {"status": "error", "message": str(ex)}


# ---- profile viewer and customizer ----
def create_profile_view(page: ft.Page, jwt_token: str, current_username: str, on_reboot_callback, api_base_url: str = API_URL ):
    new_url = None
    current_avatar = page.session.store.get("avatarUrl")or f"{API_URL}/current-avatar?token={jwt_token}" or f"{API_URL}/avatars/default-avatar.gif"
    

    avatar_img = ft.Image(
        src=f"{current_avatar}", 
        width=150, height=150, 
        fit=ft.BoxFit.COVER, 
        border_radius=75
    )

    username_field = ft.TextField(
        label="Username",
        value=current_username,
        prefix_icon=ft.Icons.PERSON
    )

    password_field = ft.TextField(
        label="New Password", 
        prefix_icon=ft.Icons.LOCK, 
        password=True, 
        can_reveal_password=True
    )
    status_text = ft.Text(value="", color=ft.Colors.RED)

    # --- Image Upload Logic ---
    async def handle_avatar_upload(e):
        file_picker = ft.FilePicker()

        files = await file_picker.pick_files(allow_multiple=False, file_type=ft.FilePickerFileType.IMAGE)
        
        if not files:
            return
            
        selected_file = files[0]
        status_text.value = "Uploading image..."
        status_text.color = ft.Colors.BLUE
        page.update()

        res = await upload_to_server(selected_file, api_base_url, IS_WEB, file_picker, current_username)

        if res.get("status") == "success":
            nonlocal new_url
            new_url = res.get("url")
            avatar_img.src = new_url
            page.session.store.set("avatarUrl", new_url) # saves to session
            status_text.value = "Successfully uploaded avatar!"
            status_text.color = ft.Colors.GREEN
        else:
            status_text.value = res.get("message", "Upload failed.")
            status_text.color = ft.Colors.RED
            
        page.update()

    def reboot():
        show_snack(page, "Rebooting UI...", ft.Colors.BLUE)
        if len(page.views) > 1:
            page.views.pop()
        page.update()
        # Reboot
        page.run_task(on_reboot_callback)

    # --- Save Profile Logic ---
    def save_profile(e):
        data_to_send = {}
        if password_field.value:
            data_to_send["password"] = password_field.value
        
        if username_field.value and username_field.value != current_username:
            data_to_send["userName"] = username_field.value

        if not data_to_send:
            status_text.value = "No changes to save. Avatar updates automatically"
            status_text.color = ft.Colors.ORANGE
            page.update()
            return

        status_text.value = "Saving..."
        status_text.color = ft.Colors.BLUE
        page.update()

        # payload to /profile
        try:
            headers = {"Authorization": f"Bearer {jwt_token}"}
            resp = requests.post(f"{api_base_url}/profile", json=data_to_send, headers=headers)
            res_data = resp.json()
            
            if res_data.get("status") == "success":
                status_text.value = "Successfully updated profile"
                status_text.color = ft.Colors.GREEN
                password_field.value = ""
                # updates token if username was changed
                if "new_token" in res_data:
                    new_name = res_data["new_username"]
                    
                    page.session.store.set("token", res_data["new_token"])
                    page.session.store.set("username", new_name)
                    
                    prefs = ft.SharedPreferences()
                    page.run_task(prefs.set, "auth_token", res_data["new_token"])
                    
                    # --- Force UI Reboot ---
                    reboot()
            else:
                status_text.value = res_data.get("message", "Failed to update profile")
                status_text.color = ft.Colors.RED
                
        except Exception as ex:
            status_text.value = f"Server error: {str(ex)}"
            status_text.color = ft.Colors.RED
            
        page.update()

    # --- Layout ---
    profile_container = ft.Container(
        content=ft.Column(
            controls=[
                ft.Text("Edit Profile", size=28, weight=ft.FontWeight.BOLD),
                ft.Divider(height=20),
                
                # Avatar part
                ft.Row(
                    controls=[
                        avatar_img,
                        ft.Button(
                            "Upload New Avatar", 
                            icon=ft.Icons.UPLOAD,
                            on_click=lambda e: page.run_task(handle_avatar_upload, e)
                        )
                    ],
                    alignment=ft.MainAxisAlignment.START,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER
                ),
                ft.Divider(height=20),
                
                # Input
                username_field,
                password_field,
                
                # Status / Submit
                status_text,
                ft.Button(
                    "Save Changes", 
                    on_click=save_profile, 
                    bgcolor=ft.Colors.GREEN, 
                    color=ft.Colors.WHITE,
                    width=200
                ),
                ft.Button(
                    "Reboot",
                    on_click=reboot,
                    bgcolor=ft.Colors.RED,
                    color=ft.Colors.WHITE,
                    width=200

                )
                 
            ],
            spacing=15,
        ),
        padding=30,
        width=600,
    )
    return profile_container

# ---- open profile view ----
def open_profile(page: ft.Page, on_reboot_callback):
    current_token = page.session.store.get("token")
    current_username = page.session.store.get("username")
    
    if not current_token or not current_username:
        show_snack(page, "You must be logged in to edit your profile.", RED)
        return

    profile_content = create_profile_view(page, current_token, current_username, on_reboot_callback, API_URL) 
    
    profile_page = ft.View(
        route="/profile",
        controls=[
            ft.AppBar(title=ft.Text("Settings & Profile", color=WHITE), bgcolor=BLACK),
            ft.Container(
                content=profile_content, 
                alignment=ft.Alignment.TOP_CENTER, 
                expand=True,
                padding=20
            )
        ],
        bgcolor=DARK_GREY
    )
    
    page.views.append(profile_page)
    page.update()

# ---- main chat UI ----
def build_chat_ui(page: ft.Page, current_username, role, initial_friends, initial_requests, sounds, on_reboot_callback):
    page.clean()
    page.horizontal_alignment = ft.CrossAxisAlignment.START
    page.vertical_alignment = ft.MainAxisAlignment.START

    ping_sound = sounds["ping"]

    def handle_notif_sound():
        show_snack(page, "playing", NEON_GREEN)
        try:
            ping_sound.seek(0) # reset audio to start
            page.run_task(ping_sound.play)  
            page.run_task(ping_sound.play)  # played twice since it doesn't want to play for the first time
            show_snack(page, "played", NEON_GREEN)
        except Exception as e:
            show_snack(page, f"Failed to play sound: {e}", RED)
            ping_sound.seek(0)
            page.run_task(sounds["error"].play)
            page.run_task(sounds["error"].play)

    def move_chat_input():
        # UP
        center_column.padding = ft.Padding(left=10, top=10, right=10, bottom=60)
        center_column.update()

        # Timed
        async def bring_it_down():
            await asyncio.sleep(3) # Wait 3 seconds
            center_column.padding = ft.Padding(left=10, top=10, right=10, bottom=10) # reset to 10
            center_column.update()

        page.run_task(bring_it_down)

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

        current_token = page.session.store.get("token")
        if not current_token:
            show_snack(page, "Error: Missing auth token", RED)
            return
        
        # remove notif when clicked on user
        for tile in user_list.controls:
            if tile.title.value == friend_name:
                tile.trailing.visible = False
                page.update()
                break
        # Fetch history from DB
        # --auth--
        headerss = {"Authorization": f"Bearer {current_token}"}
        try:
            res = requests.get(f"{API_URL}/messages", params={"user1": current_username, "user2": friend_name}, headers=headerss).json()
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
            show_snack(page, f"Couldn't load chat history: {e}", RED)

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
            show_snack(page, "Couldn't check user status.", RED)
            return False
        
    def add_friend_to_ui(friend_name):
        if not friend_name or friend_name == "None":
            return

        if friend_name not in app_state["local_chat_history"]:
            app_state["local_chat_history"][friend_name] = []

        # fetch from session
        live_username = page.session.store.get("username")
        my_avatar = page.session.store.get("avatarUrl")

        # notif
        notification_badge = ft.Container(
            content=ft.Text("New", size=10, color=WHITE, weight="bold"),
            bgcolor=RED,
            padding=ft.padding.only(left=6, right=6, top=2, bottom=2),
            border_radius=10,
            visible=False # hide by default
        )

        if live_username and friend_name.lower() == live_username.lower() and my_avatar:
            # Render uploaded img
            leading_avatar = ft.Image(
                src=my_avatar, 
                width=40, 
                height=40, 
                fit=ft.BoxFit.COVER, 
                border_radius=20
            )
        else:
            # placeholder for others
            leading_avatar = ft.CircleAvatar(bgcolor=NEON_GREEN, content=ft.Icon(ft.Icons.PERSON, color=BLACK))

        tile = ft.ListTile(
            leading=leading_avatar,
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
                    show_snack(page, f"New friend: {requester}!", NEON_GREEN)
                    move_chat_input()
                    handle_notif_sound()
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
                    show_snack(page, f"New message from {sender}", NEON_GREEN)
                    move_chat_input()
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
                    show_snack(page, f"New friend request from {requester_name}!", NEON_GREEN)
            
            elif isinstance(data, dict) and data.get("type") == "friend_accepted":
                add_friend_to_ui(data.get("friend"))
                handle_notif_sound()
                show_snack(page, f"{data.get('friend')} accepted your request!", NEON_GREEN)
            
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
            show_snack(page, "WebSocket Disconnected.", RED)
            page.update()
        current_token = page.session.store.get("token")
        ws = js.WebSocket.new(f"wss://{SERVER_DOMAIN}/ws/{current_username}?token={current_token}")
        ws.onmessage = create_proxy(on_ws_message)
        ws.onclose = create_proxy(on_ws_disconnect)
        
        app_state["ws_connection"] = ws 
    else:
        # VSC / Desktop  (Standard Python connection)
        current_token = page.session.store.get("token")
        async def desktop_ws():
            WS_URL = f"wss://{SERVER_DOMAIN}/ws/{current_username}?token={current_token}"
            try:
                async with websockets.connect(WS_URL) as websocket:
                    app_state["ws_connection"] = websocket 
                    while True:
                        msg_raw = await websocket.recv()
                        process_incoming_message(json.loads(msg_raw))
            except Exception as e:
                print(f"WS Connection Error: {e}")
                show_snack(page, "Lost connection, restart required ig", RED)

        page.run_task(desktop_ws)

    # --- Friend Search ---
    friend_search_field = ft.TextField(label="Find User", border_color=RED_MAGENTA, height=45)
    def send_friend_request(e):
        target = friend_search_field.value
        if not target or target == current_username: return
        current_token = page.session.store.get("token")
        headerss = {"Authorization": f"Bearer {current_token}"}
        res = requests.post(f"{API_URL}/friend-request", json={"from": current_username, "to": target}, headers=headerss).json()
        if res.get("status") == "success":
            show_snack(page, f"Sent to {target}!", NEON_GREEN)
            friend_search_field.value = ""
        else:
            show_snack(page, res.get("message"), RED)
        page.update()

    # --- File Uploader ---
    async def on_image_picked(e):
        file_picker = ft.FilePicker()
        

        files = await file_picker.pick_files(allow_multiple=False)
        if not files or not app_state.get("active_chat"):
            return
            
        f = files[0] 
        friend = app_state["active_chat"]
        
        show_snack(page, "Uploading image...", NEON_GREEN) 

        res = await upload_to_server(f, API_URL, IS_WEB, file_picker, current_username, receiver=friend)

        if res.get("status") == "success":
            if not IS_WEB:
                img_url = res["url"] 
                msg_text = f"[IMG]{img_url}"
                
                # save to cache
                app_state["local_chat_history"][friend].append({"sender": current_username, "content": msg_text})
                
                bubble = parse_message_to_ui("You", msg_text, NEON_GREEN) 
                chat_display.controls.append(bubble)
                page.update()

                payload = {"type": "chat_message", "to": friend, "content": msg_text}
                if app_state.get("ws_connection"):
                    await app_state["ws_connection"].send(json.dumps(payload))
        else:
            show_snack(page, res.get("message", "Upload failed"), ft.Colors.RED)

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
    attach_btn = ft.IconButton(icon=ft.Icons.IMAGE, icon_color=WHITE, on_click=lambda e: page.run_task(on_image_picked, e))
    chat_input_row = ft.Row(controls=[attach_btn, chat_input, send_btn])

    def send_msg(e):
        if chat_input.value and app_state["active_chat"]:
            msg_text = chat_input.value
            friend = app_state["active_chat"]
            
            app_state["local_chat_history"][friend].append({"sender": current_username, "content": msg_text})
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
            ft.Button("Send Request", on_click=send_friend_request, bgcolor=RED_MAGENTA, color=WHITE),
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
            ft.Button("Back", on_click=lambda e: toggle_admin_view(False), bgcolor=DARK_GREY, color=WHITE)
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
                current_token = page.session.store.get("token")
                headerss = {"Authorization": f"Bearer {current_token}"}
                try:
                    res = requests.get(f"{API_URL}/all-users", params={"requester_role": app_state["role"]}, headers=headerss).json()
                    
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
                    show_snack(page, f"Failed to load users: {e}", RED)
                    
            else:
                right_sidebar_content.content = add_friend_view
            
            page.update()

    # triggered by star button
    def promote_to_admin(target_username):
        payload = {"requester": current_username, "target": target_username}
        current_token = page.session.store.get("token")
        headerss = {"Authorization": f"Bearer {current_token}"}
        try:
            res = requests.post(f"{API_URL}/promote", json=payload, headers=headerss).json()
            if res.get("status") == "success":
                show_snack(page, res.get("message"), NEON_GREEN)
                # Refresh
                toggle_admin_view(True) 
            else:
                show_snack(page, res.get("message"), RED)
        except Exception as e:
            show_snack(page, f"Failed to connect to server: {e}", RED)

    # switch
    if app_state.get("role") == "admin":
        add_friend_view.controls.insert(0, ft.Button(
            "show all users", 
            bgcolor=RED, 
            color=WHITE, 
            on_click=lambda e: toggle_admin_view(True)
        ))
    
    # --- Desktop UI ---
    left_column = ft.Container(
        col={"xs": 12, "md": 3, "lg": 2, "xl": 2},
        expand=True,
        padding=10,
        border=ft.border.all(1, RED_MAGENTA),
        content=ft.Column([
            ft.Row([
                ft.Text("Friends List", color=WHITE, weight="bold"),
                ft.IconButton(ft.Icons.SETTINGS, icon_color=ft.Colors.WHITE54, on_click=lambda e: open_profile(page, on_reboot_callback))
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            user_list
        ])
    )

    center_column = ft.Container(
        col={"xs": 12, "md": 6, "lg": 7, "xl": 8},
        expand=True,
        padding=ft.Padding(left=10, top=10, right=10, bottom=10),
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
            ft.IconButton(ft.Icons.MANAGE_ACCOUNTS, icon_color=NEON_GREEN, on_click=lambda e: open_profile(page, on_reboot_callback)),
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

# ---- MAIN ----
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

    sounds = {"ping": ping_sound, "error": error_sound, "wb": WB_sound}

    # returns to prev screen
    def view_pop(view):
        page.views.pop()
        top_view = page.views[-1]
        page.go(top_view.route)
    page.on_view_pop = view_pop

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
                        title.value = "call error, Retrying..."
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
    def handle_register(e):
        if not email_field.value or not user_field.value or not pass_field.value:
            show_snack(page, "some Field is missing", RED)
            return
            
        payload = {"email": email_field.value, "userName": user_field.value, "password": pass_field.value}
        try:
            response = requests.post(f"{API_URL}/register", json=payload, timeout=5)
            try:
                res = response.json()
            except ValueError:
                show_snack(page, "Couldn't reach server (Proxy eror).", RED)
                return

            if res.get("status") == "success":
                show_snack(page, "Register success, please log in", NEON_GREEN)
            else:
                show_snack(page, res.get("detail", res.get("message", "Registration failed")), RED)
                
        except requests.exceptions.RequestException:
            show_snack(page, "Couldn't reach server.", RED)

    def handle_login(e):
        if not user_field.value or not pass_field.value:
            show_snack(page, "Username and Password required!", RED)
            return

        payload = {"userName": user_field.value, "password": pass_field.value}
        try:
            response = requests.post(f"{API_URL}/login", json=payload, timeout=5)
            try:
                res = response.json()
            except ValueError:
                show_snack(page, "Couldn't reach server (Proxy error)", RED)
                return

            if res.get("status") == "success":
                username = res.get("username", user_field.value)
                
                
                # save token if accepted cookies
                page.session.store.set("token", res.get("token"))
                page.session.store.set("username", username)
                
                async def save_token():
                    if await prefs.get("cookies_accepted"):
                        await prefs.set("auth_token", res.get("token"))

                page.run_task(save_token)

                build_chat_ui(
                    page,
                    username, 
                    res.get("role", "user"),
                    res.get("friends", []), 
                    res.get("friendRequests", []),
                    sounds,
                    boot_app
                )
            else:
                show_snack(page, res.get("message", "Invalid login details"), RED)
                
        except requests.exceptions.RequestException:
            show_snack(page, "Couldn't reach server.", RED)


    # --- Login/register Screen ---
    login_btn = ft.Button("Login", on_click=handle_login, style=ft.ButtonStyle(bgcolor=RED_MAGENTA, color=WHITE))
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
                    ft.Button("Accept", on_click=accept_cookies, bgcolor=NEON_GREEN, color=BLACK)
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
                    
                    username = res.get("username")
                    page.session.store.set("token", saved_token)
                    page.session.store.set("username", username)
                    # fetch avatar
                    try:
                        headers = {"Authorization": f"Bearer {saved_token}"} 
                        avatar_resp = requests.get(f"{API_URL}/current-avatar", headers=headers, timeout=5).json()
                        if avatar_resp.get("status") == "success" and avatar_resp.get("avatarUrl"):
                            page.session.store.set("avatarUrl", avatar_resp.get("avatarUrl"))
                        else:
                            page.session.store.set("avatarUrl", f"{API_URL}/avatars/default-avatar.gif")
                    except Exception:
                        page.session.store.set("avatarUrl", f"{API_URL}/avatars/default-avatar.gif")

                    # this will unlock audio on web since browser can't play mp3 until user interacts with the app
                    def unlock_audio_and_enter(e):
                        # play nothing - just so it can work
                        page.run_task(WB_sound.play)
                    
                        # Build the UI
                        build_chat_ui(
                            page,
                            username, 
                            res.get("role", "user"), 
                            res.get("friends", []), 
                            res.get("friendRequests", []),
                            sounds,
                            boot_app
                        )

                    async def force_logout(e):
                        # clear memory
                        page.session.store.clear()
                        # clear cookie
                        await prefs.remove("auth_token")
                        
                        show_snack(page, "Token cleared. Please log in again.", ft.Colors.GREEN)
                        
                        # clear and boot to login page
                        page.clean()
                        page.add(login_card)
                        page.update()

                    # WB screen
                    page.clean()
                    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
                    page.vertical_alignment = ft.MainAxisAlignment.CENTER
                    page.add(
                        ft.Column(
                            controls=[
                                ft.Icon(ft.Icons.CHECK_CIRCLE, color=NEON_GREEN, size=60),
                                ft.Text(f"Welcome back, {res.get('username')}!", size=24, color=WHITE, weight="bold"),
                                ft.Button(
                                    "Enter Chat", 
                                    bgcolor=RED_MAGENTA, 
                                    color=WHITE, 
                                    on_click=unlock_audio_and_enter # unlock
                                ),
                                ft.Button(
                                    "Logout", 
                                    bgcolor=DARK_GREY, 
                                    color=WHITE, 
                                    on_click=force_logout 
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

# run main app
ft.run(main)
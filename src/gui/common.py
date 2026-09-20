"""Small pieces shared by the panels."""
from nicegui import ui


async def confirm(message, confirm_label="Confirm"):
    """Ask for a confirmation; returns True or False."""
    with ui.dialog() as dialog, ui.card():
        ui.label(message).classes("whitespace-pre-line")
        with ui.row().classes("w-full justify-end"):
            ui.button("Cancel", on_click=lambda: dialog.submit(False)).props("flat")
            ui.button(confirm_label, on_click=lambda: dialog.submit(True)).props("color=negative").mark("confirm")
    return await dialog


def notify_error(message):
    ui.notify(message, type="negative", multi_line=True)


def notify_problems(title, problems, limit=12):
    text = "\n".join(problems[:limit]) + (f"\n... and {len(problems) - limit} more" if len(problems) > limit else "")
    ui.notify(f"{title}\n{text}", type="warning", multi_line=True, close_button=True, timeout=0)


def section_title(text):
    return ui.label(text).classes("text-lg font-medium")

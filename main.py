import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
import flet as ft

cred = credentials.Certificate("config.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

class Task(ft.UserControl):
    def __init__(self, task_name, task_status_change, task_delete, doc_ref=None):
        super().__init__()
        self.completed = False
        self.task_name = task_name
        self.task_status_change = task_status_change
        self.task_delete = task_delete
        self.doc_ref = doc_ref

    def get_page(self):
        ancestor = self
        while ancestor:
            if isinstance(ancestor, ft.Page):
                return ancestor
            ancestor = ancestor.parent
        return None

    def build(self):
        self.display_task = ft.Checkbox(
            value=self.completed,
            label=self.task_name,
            on_change=self.status_changed
        )
        self.edit_name = ft.TextField(expand=1)
        self.display_view = ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                self.display_task,
                ft.Row(
                    spacing=0,
                    controls=[
                        ft.IconButton(
                            icon=ft.icons.CREATE_OUTLINED,
                            tooltip="Edit To-Do",
                            on_click=self.edit_clicked,
                        ),
                        ft.IconButton(
                            ft.icons.DELETE_OUTLINE,
                            tooltip="Delete To-Do",
                            on_click=self.delete_clicked,
                        ),
                    ],
                ),
            ],
        )
        self.edit_view = ft.Row(
            visible=False,
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                self.edit_name,
                ft.IconButton(
                    icon=ft.icons.DONE_OUTLINE_OUTLINED,
                    icon_color=ft.colors.GREEN,
                    tooltip="Update To-Do",
                    on_click=self.save_clicked,
                ),
            ],
        )
        return ft.Column(controls=[self.display_view, self.edit_view])

    async def edit_clicked(self, e):
        self.edit_name.value = self.display_task.label
        self.display_view.visible = False
        self.edit_view.visible = True
        if self.doc_ref:
            self.doc_ref.update({'task_name': self.edit_name.value})
        page = self.get_page()
        if page:
            await page.update_async()

    async def save_clicked(self, e):
        self.display_task.label = self.edit_name.value
        self.display_view.visible = True
        self.edit_view.visible = False
        if self.doc_ref:
            self.doc_ref.update({'task_name': self.edit_name.value})
        await self.update_async()

    async def status_changed(self, e):
        self.completed = self.display_task.value
        if self.doc_ref:
            self.doc_ref.update({'completed': self.completed})
        await self.task_status_change(self)
        await self.update_async()

    async def delete_clicked(self, e):
        if self.doc_ref:
            self.doc_ref.delete()
        await self.task_delete(self)
        await self.update_async()

class TodoApp(ft.UserControl):
    def __init__(self, doc_ref=None):
        super().__init__()
        self.doc_ref = doc_ref
        self.tasks = []
        self.task_container = ft.Column()
    def build(self):
        self.new_task = ft.TextField(
            hint_text="What needs to be done?", on_submit=self.add_clicked, expand=True
        )
        self.filter = ft.Tabs(
            scrollable=False,
            selected_index=0,
            on_change=self.tabs_changed,
            tabs=[ft.Tab(text="all"), ft.Tab(text="active"), ft.Tab(text="completed")],
        )
        self.items_left = ft.Text("0 items left")
        return ft.Column(
            width=600,
            controls=[
                ft.Row(
                    [ft.Text(value="Todos", style=ft.TextThemeStyle.HEADLINE_MEDIUM)],
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                ft.Row(
                    controls=[
                        self.new_task,
                        ft.FloatingActionButton(
                            icon=ft.icons.ADD, on_click=self.add_clicked
                        ),
                    ],
                ),
                ft.Column(
                    spacing=25,
                    controls=[
                        self.filter,
                        self.task_container,
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                self.items_left,
                                ft.OutlinedButton(
                                    text="Clear completed", on_click=self.clear_clicked
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        )

    async def add_clicked(self, e):
        if self.new_task.value:
            doc_ref = db.collection('tasks').add({'task_name': self.new_task.value, 'completed': False})[1]
            task = Task(self.new_task.value, self.task_status_change, self.task_delete, doc_ref)
            self.add_task(task)
            self.new_task.value = ""
            await self.new_task.focus_async()
            await self.update_async()

    def add_task(self, task):
        self.tasks.append(task)
        self.task_container.controls.append(task.build())

    async def task_status_change(self, task):
        await self.update_async()

    async def task_delete(self, task):
        self.tasks.remove(task)
        self.task_container.controls.remove(task.build())
        await self.update_async()

    async def tabs_changed(self, e):
        await self.filter_tasks()
        await self.update_async()

    async def filter_tasks(self):
        status = self.filter.tabs[self.filter.selected_index].text.lower()
        if status == "all":
            filtered_tasks = self.tasks
        elif status == "active":
            filtered_tasks = [task for task in self.tasks if not task.completed]
        elif status == "completed":
            filtered_tasks = [task for task in self.tasks if task.completed]
        else:
            raise ValueError("Invalid status filter")

        self.task_container.controls = [task.build() for task in filtered_tasks]
        await self.update_async()

    async def clear_clicked(self, e):
        for task in self.tasks[:]:
            if task.completed:
                await self.task_delete(task)

    async def update_async(self):
        status = self.filter.tabs[self.filter.selected_index].text
        count = sum(1 for task in self.tasks if not task.completed)
        self.items_left.value = f"{count} active item(s) left"
        await super().update_async()

async def main(page: ft.Page):
    async def task_status_change_callback(task):
        if task.doc_ref:
            task.doc_ref.update({'completed': task.completed})

    async def task_delete_callback(task):
        if task.doc_ref:
            task.doc_ref.delete()

    tasks_ref = db.collection('tasks')
    tasks_snapshot = tasks_ref.get()
    tasks = []

    for task_doc in tasks_snapshot:
        task_data = task_doc.to_dict()
        print("Task data:", task_data)
        task = Task(task_data['task_name'], task_status_change_callback, task_delete_callback, task_doc.reference)
        tasks.append(task)

    todo_app = TodoApp()

    for task in tasks:
        todo_app.add_task(task)
        
    page.title = "ToDo App"
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.scroll = ft.ScrollMode.ADAPTIVE
    await page.add_async(todo_app)

ft.app(main)

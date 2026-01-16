"""
Application registry for managing multiple apps.

Provides a central registry for app instances, allowing
the main loop to launch apps by ID and track their order.
"""


class AppRegistry:
    def __init__(self):
        self._apps = {}
        self._order = []

    def register(self, app_id, app_instance, name=None):
        self._apps[app_id] = app_instance
        if app_id not in self._order:
            self._order.append(app_id)
        if name:
            app_instance.name = name # Attach name to instance if needed

    def get_app(self, app_id):
        return self._apps.get(app_id)

    def get_all_apps(self):
        return [self._apps[mid] for mid in self._order]

    def get_app_names(self):
        # Assumes apps have a name attribute or we map them
        return [(mid, self._apps[mid].name if hasattr(self._apps[mid], 'name') else mid) for mid in self._order]

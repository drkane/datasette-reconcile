from datasette.version import __version__
from datasette.views.base import BaseView

from datasette_reconcile.utils import check_config, check_permissions


class ReconcileHTML(BaseView):
    name = "reconcile_html"

    async def get(self, request):
        database = request.url_vars["db_name"]
        table = request.url_vars["db_table"]
        db = self.ds.get_database(database)

        # get plugin configuration
        config = self.ds.plugin_config("datasette-reconcile", database=database, table=table)
        config = await check_config(config, db, table)

        # check user can at least view this table
        await check_permissions(
            request,
            [
                ("view-table", (database, table)),
                ("view-database", database),
                "view-instance",
            ],
            self.ds,
        )

        return await self.render(
            ["reconcile.html"],
            request=request,
            context={
                "database": database,
                "table": table,
                "reconcile_config": config,
                "reconcile_url": self.ds.absolute_url(request, self.ds.urls.table(database, table) + "/-/reconcile"),
                "metadata": self.ds.metadata(),
                "datasette_version": __version__,
                "private": not await self.ds.permission_allowed(None, "view-instance"),
            },
        )

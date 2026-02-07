from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class CustomPagination(PageNumberPagination):
    page_size = 10  # The number of items per page
    page_size_query_param = (
        "size"  # Allow clients to change the page size using a query parameter
    )
    max_page_size = 100  # Maximum page size

    def get_paginated_response(self, data):
        return Response(
            {
                "count": self.page.paginator.count,  # Total number of items
                "next": self.get_next_link(),  # URL for the next page
                "previous": self.get_previous_link(),  # URL for the previous page
                "results": data,  # Paginated data (list of deals)
            }
        )

import django_filters
from assistant.storage.models import WikiDocument


class WikiDocumentFilter(django_filters.FilterSet):
    bot = django_filters.CharFilter(field_name='bot__codename', lookup_expr='exact')

    class Meta:
        model = WikiDocument
        fields = ['bot']

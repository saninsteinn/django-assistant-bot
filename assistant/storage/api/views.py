from django_filters.rest_framework import DjangoFilterBackend
from drf_yasg.utils import swagger_auto_schema
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from assistant.storage.api.filters import WikiDocumentFilter
from assistant.storage.api.pagination import DefaultPagination
from assistant.storage.api.serializers import WikiDocumentSerializer
from assistant.storage.models import WikiDocument


class WikiDocumentViewSet(viewsets.ModelViewSet):
    queryset = WikiDocument.objects.select_related('bot').prefetch_related('processing').order_by('id')
    serializer_class = WikiDocumentSerializer
    pagination_class = DefaultPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = WikiDocumentFilter

    @swagger_auto_schema(
        method='post',
        request_body=WikiDocumentSerializer(many=True),
        responses={201: 'bulk create successful'}
    )
    @action(detail=False, methods=['post'])
    def bulk(self, request):
        serializer = self.get_serializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)
        serializer.create(serializer.validated_data)
        return Response(status=status.HTTP_201_CREATED)

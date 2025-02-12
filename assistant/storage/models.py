from django.db import models
from mptt.fields import TreeForeignKey
from mptt.models import MPTTModel
from pgvector.django import VectorField, HnswIndex


class Document(models.Model):
    wiki = models.ForeignKey('WikiDocument', on_delete=models.CASCADE, related_name='documents', null=True, blank=True)
    processing = models.ForeignKey('WikiDocumentProcessing', on_delete=models.CASCADE, related_name='documents', null=True, blank=True)
    name = models.TextField()
    description = models.TextField(default='', blank=True)
    content = models.TextField(default='', blank=True)
    content_embedding = VectorField(dimensions=768, blank=True, null=True)  # for RuBert

    def __str__(self):
        return self.wiki.path.replace(' / ', '. ') if hasattr(self, 'parent') else self.name


class BaseEmbeddingModel(models.Model):
    document = models.ForeignKey('Document', on_delete=models.CASCADE, related_name='%(class)ss')
    text = models.TextField()
    order = models.PositiveIntegerField()
    embedding = VectorField(dimensions=768, blank=True, null=True)  # for RuBert

    class Meta:
        abstract = True

    def __str__(self):
        return self.text


class Sentence(BaseEmbeddingModel):

    class Meta:
        indexes = [
            HnswIndex(
                name="sentence_embedding_index",
                fields=["embedding"],
                m=16,
                ef_construction=64,
                opclasses=["vector_cosine_ops"],
            )
            # GistIndex(fields=['embedding'], name='sentence_embedding_gist_idx'),
        ]


class Question(BaseEmbeddingModel):

    class Meta:
        indexes = [
            HnswIndex(
                name="question_embedding_index",
                fields=["embedding"],
                m=16,
                ef_construction=64,
                opclasses=["vector_cosine_ops"],
            )
        ]


class WikiDocument(MPTTModel):
    bot = models.ForeignKey('assistant_bot.Bot', on_delete=models.CASCADE, related_name='wikis', null=True, blank=True)
    parent = TreeForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')
    url = models.URLField(blank=True, null=True, verbose_name="URL")
    title = models.TextField(blank=True, verbose_name="Заголовок")
    description = models.TextField(default='', blank=True, verbose_name="Описание")
    content = models.TextField(default='', blank=True, verbose_name="Содержание")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    def __str__(self):
        return f"{self.title}"

    @property
    def path(self) -> str:
        return ' / '.join([str(i) for i in self.get_ancestors(include_self=True)])


class WikiDocumentProcessing(models.Model):

    class Status(models.TextChoices):
        IN_PROGRESS = 'in_progress', 'In progress'
        COMPLETED = 'completed', 'Completed'
        FAILED = 'failed', 'Failed'

    wiki_document = models.ForeignKey('WikiDocument', on_delete=models.CASCADE, related_name='processing')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.IN_PROGRESS)

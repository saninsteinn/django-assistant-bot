
from django.contrib import admin
from django.db.models import F
from django.urls import reverse
from django.utils.html import format_html

from assistant.admin.admin import SuperUserMixin
from assistant.storage.models import Document, WikiDocument, Sentence, Question


# Register your models here.

# @admin.register(Document, site=admin_site)
class DocumentAdmin(SuperUserMixin, admin.ModelAdmin):
    list_display = ('id', 'name', 'section_display', 'description')
    ordering = ('id',)
    readonly_fields = ('sentences_display', 'questions_display')
    exclude = ('sentences', 'questions')

    def section_display(self, obj):
        url = reverse('admin:storage_wikidocument_change', args=[obj.wiki.id])
        return format_html('<a href="{}">{}</a>', url, obj.wiki)
    section_display.short_description = 'Section'

    def sentences_display(self, obj):
        return format_html('<pre>{}</pre>', '\n'.join(obj.sentences))
    sentences_display.short_description = 'Sentences'

    def questions_display(self, obj):
        return format_html('<pre>{}</pre>', '\n'.join(obj.questions))
    questions_display.short_description = 'Questions'



# @admin.register(WikiDocument, site=admin_site)
class WikiDocumentAdmin(SuperUserMixin, admin.ModelAdmin):
    list_display = ('id', 'path', 'content', 'documents', 'processing', 'created_at')
    ordering = ('id',)

    list_filter = ('bot__codename', 'processing__status')
    actions = ('process',)

    def documents(self, obj):
        return format_html(
            '<a href="{}?wiki__id__exact={}">Documents ({})</a>',
            reverse('admin:storage_document_changelist'),
            obj.id,
            obj.documents.count(),
        )
    documents.short_description = 'Documents'

    def processing(self, obj):
        p = obj.processing.order_by('-id').first()
        return p.status if p else '-'
    processing.short_description = 'Processing'

    def process(self, request, queryset):
        for wiki in queryset:
            wiki.save(update_fields=['updated_at'])  # dummy update to trigger signal
    process.short_description = 'Process'



# @admin.register(Sentence, site=admin_site)
class SentenceAdmin(admin.ModelAdmin):
    list_display = ('id', 'text', 'order')


# @admin.register(Question, site=admin_site)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('id', 'text', 'order')


from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User

from .models import Category, Comment, Location, Post

admin.site.unregister(User)


@admin.register(User)
class UserAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff')


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('title', 'slug', 'is_published', 'created_at')
    list_editable = ('is_published',)
    list_filter = ('is_published', 'created_at')
    search_fields = ('title',)
    prepopulated_fields = {'slug': ('title',)}


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_published', 'created_at')
    list_editable = ('is_published',)
    list_filter = ('is_published', 'created_at')
    search_fields = ('name',)


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'post', 'author', 'created_at')
    list_editable = ('post',)
    list_filter = ('author', 'created_at')
    search_fields = ('text', 'author__username')


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'pub_date',
        'author',
        'category',
        'location',
        'is_published',
    )
    list_editable = (
        'is_published',
        'category',
        'location',
    )
    list_filter = (
        'is_published',
        'category',
        'location',
        'pub_date',
        'author',
    )
    search_fields = ('title', 'text')
    date_hierarchy = 'pub_date'
    empty_value_display = 'Планета Земля'

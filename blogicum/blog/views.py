from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.http import Http404
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.generic import (
    CreateView, DeleteView, DetailView, ListView, UpdateView,
)

from .forms import UserEditForm, PostForm, CommentForm
from .models import Post, Category, Comment

LOCATION_DEFAULT = 'Планета Земля'
User = get_user_model()


def annotate_and_order_posts(queryset):
    return queryset.select_related(
        'author', 'category', 'location'
    ).annotate(
        comment_count=Count('comments')
    ).order_by(*Post._meta.ordering)


def get_published_posts():
    now = timezone.now()
    published_qs = Post.objects.filter(
        is_published=True,
        category__is_published=True,
        pub_date__lte=now
    )
    return annotate_and_order_posts(published_qs)


def check_post_visibility(post, user):
    if user == post.author:
        return True
    now = timezone.now()
    if (
        post.is_published
        and post.pub_date <= now
        and post.category.is_published
    ):
        return True
    return False


class IndexView(ListView):
    model = Post
    template_name = 'blog/index.html'
    paginate_by = 10

    def get_queryset(self):
        return get_published_posts()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.filter(is_published=True)
        context['location_default'] = LOCATION_DEFAULT
        return context


class CategoryPostsView(ListView):
    model = Post
    template_name = 'blog/category.html'
    paginate_by = 10

    def dispatch(self, request, *args, **kwargs):
        self.category = get_object_or_404(
            Category, slug=self.kwargs['category_slug'], is_published=True
        )
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return get_published_posts().filter(category=self.category)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['category'] = self.category
        context['categories'] = Category.objects.filter(is_published=True)
        context['location_default'] = LOCATION_DEFAULT
        return context


class PostDetailView(DetailView):
    model = Post
    template_name = 'blog/detail.html'
    context_object_name = 'post'
    pk_url_kwarg = 'post_id'

    def get_object(self, queryset=None):
        post = get_object_or_404(
            Post.objects.select_related('author', 'category', 'location'),
            pk=self.kwargs['post_id']
        )
        if not check_post_visibility(post, self.request.user):
            raise Http404("Публикация еще не опубликована.")
        return post

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        post = context['post']
        context['categories'] = Category.objects.filter(is_published=True)
        context['comments'] = post.comments.select_related('author').all()
        context['form'] = CommentForm()
        context['location_default'] = LOCATION_DEFAULT
        return context


class ProfileView(ListView):
    model = Post
    template_name = 'blog/profile.html'
    context_object_name = 'posts'
    paginate_by = 10

    def dispatch(self, request, *args, **kwargs):
        self.profile = get_object_or_404(
            User,
            username=self.kwargs['username'])
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        qs = annotate_and_order_posts(self.profile.posts.all())

        if self.request.user == self.profile:
            return qs

        now = timezone.now()
        return qs.filter(
            is_published=True,
            category__is_published=True,
            pub_date__lte=now
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['profile'] = self.profile
        context['location_default'] = LOCATION_DEFAULT
        return context


class EditProfileView(LoginRequiredMixin, UpdateView):
    model = User
    form_class = UserEditForm
    template_name = 'blog/user.html'

    def get_object(self, queryset=None):
        return self.request.user

    def get_success_url(self):
        return reverse(
            'blog:profile',
            kwargs={'username': self.object.username}
        )


class PostCreateView(LoginRequiredMixin, CreateView):
    model = Post
    form_class = PostForm
    template_name = 'blog/create.html'

    def form_valid(self, form):
        form.instance.author = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse(
            'blog:profile',
            kwargs={'username': self.request.user.username}
        )


class PostUpdateView(LoginRequiredMixin, UpdateView):
    model = Post
    form_class = PostForm
    template_name = 'blog/create.html'
    pk_url_kwarg = 'post_id'

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        if request.user != self.object.author:
            return redirect('blog:post_detail', post_id=self.object.id)
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse('blog:post_detail', kwargs={'post_id': self.object.id})


class PostDeleteView(LoginRequiredMixin, DeleteView):
    model = Post
    template_name = 'blog/create.html'
    pk_url_kwarg = 'post_id'

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        if request.user != self.object.author:
            return redirect('blog:post_detail', post_id=self.object.id)
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse(
            'blog:profile',
            kwargs={'username': self.request.user.username}
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = PostForm(instance=self.object)
        return context


def _get_post_for_comment_or_404(request, post_id: int) -> Post:
    post = get_object_or_404(
        Post.objects.select_related('author', 'category'),
        pk=post_id,
    )
    if not check_post_visibility(post, request.user):
        raise Http404("Публикация еще не опубликоваna.")
    return post


@login_required
def add_comment(request, post_id):
    post = _get_post_for_comment_or_404(request, post_id)
    form = CommentForm(request.POST or None)
    if form.is_valid():
        Comment.objects.create(
            post=post,
            author=request.user,
            text=form.cleaned_data['text'],
        )
    return redirect('blog:post_detail', post_id=post.id)


@login_required
def edit_comment(request, post_id, comment_id):
    post = _get_post_for_comment_or_404(request, post_id)
    comment = get_object_or_404(Comment, pk=comment_id, post=post)

    if comment.author != request.user:
        raise PermissionDenied

    form = CommentForm(request.POST or None, instance=comment)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('blog:post_detail', post_id=post.id)

    return render(
        request, 'blog/comment.html', {'form': form, 'comment': comment}
    )


class CommentDeleteView(LoginRequiredMixin, DeleteView):
    model = Comment
    template_name = 'blog/comment.html'
    context_object_name = 'comment'
    pk_url_kwarg = 'comment_id'

    def get_queryset(self):
        return Comment.objects.select_related('author', 'post')

    def dispatch(self, request, *args, **kwargs):
        post = _get_post_for_comment_or_404(
            request, kwargs['post_id']
        )
        self.comment_post = post
        comment = self.get_object()
        if comment.author != request.user:
            raise PermissionDenied
        if comment.post_id != post.id:
            raise Http404
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse(
            'blog:post_detail',
            kwargs={'post_id': self.comment_post.id}
        )

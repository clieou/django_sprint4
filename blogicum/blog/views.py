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
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

from .forms import UserEditForm, PostForm, CommentForm
from .models import Post, Category, Comment

LOCATION_DEFAULT = 'Планета Земля'

User = get_user_model()


def index(request):
    return IndexView.as_view()(request)


class IndexView(ListView):
    model = Post
    template_name = 'blog/index.html'
    paginate_by = 10

    def get_queryset(self):
        return (
            Post.objects.published()
            .select_related('author', 'category', 'location')
            .order_by('-pub_date')
            .annotate(comment_count=Count('comments'))
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.filter(is_published=True)
        context['location_default'] = LOCATION_DEFAULT
        return context


def category_posts(request, category_slug):
    return CategoryPostsView.as_view()(request, category_slug=category_slug)


class CategoryPostsView(ListView):
    model = Post
    template_name = 'blog/category.html'
    paginate_by = 10

    def dispatch(self, request, *args, **kwargs):
        self.category = get_object_or_404(
            Category.objects.filter(is_published=True),
            slug=self.kwargs['category_slug']
        )
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return (
            Post.objects.published()
            .select_related('author', 'category', 'location')
            .filter(category=self.category)
            .order_by('-pub_date')
            .annotate(comment_count=Count('comments'))
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['category'] = self.category
        context['categories'] = Category.objects.filter(is_published=True)
        context['location_default'] = LOCATION_DEFAULT
        return context


def post_detail(request, pk):
    return PostDetailView.as_view()(request, pk=pk)


def _is_public_post(post: Post) -> bool:
    now = timezone.now()
    return (
        post.is_published
        and post.pub_date <= now
        and post.category is not None
        and post.category.is_published
    )


class PostDetailView(DetailView):
    model = Post
    template_name = 'blog/detail.html'
    context_object_name = 'post'

    def get_queryset(self):
        return Post.objects.select_related('author', 'category', 'location')

    def get_object(self, queryset=None):
        post = super().get_object(queryset=queryset)
        if self.request.user == post.author:
            return post
        if not _is_public_post(post):
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
            username=self.kwargs['username'],
        )
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        qs = (
            Post.objects.select_related('author', 'category', 'location')
            .filter(author=self.profile)
            .order_by('-pub_date')
            .annotate(comment_count=Count('comments'))
        )

        is_owner = (
            self.request.user.is_authenticated
            and self.request.user == self.profile
        )
        if is_owner:
            return qs

        return qs.published().order_by('-pub_date')

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
            kwargs={'username': self.object.username},
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
            kwargs={'username': self.request.user.username},
        )


class PostUpdateView(LoginRequiredMixin, UpdateView):
    model = Post
    form_class = PostForm
    template_name = 'blog/create.html'
    pk_url_kwarg = 'post_id'

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        if request.user != self.object.author:
            return redirect('blog:post_detail', pk=self.object.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse('blog:post_detail', kwargs={'pk': self.object.pk})


class PostDeleteView(LoginRequiredMixin, DeleteView):
    model = Post
    template_name = 'blog/create.html'
    pk_url_kwarg = 'post_id'

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        if request.user != self.object.author:
            return redirect('blog:post_detail', pk=self.object.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse(
            'blog:profile',
            kwargs={'username': self.request.user.username},
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = PostForm(instance=self.object)
        return context


def _get_post_for_comment_or_404(*, request, post_id: int) -> Post:
    post = get_object_or_404(
        Post.objects.select_related('author', 'category'),
        pk=post_id,
    )
    if request.user != post.author and not _is_public_post(post):
        raise Http404("Публикация еще не опубликована.")
    return post


@login_required
def add_comment(request, post_id):
    post = _get_post_for_comment_or_404(request=request, post_id=post_id)

    form = CommentForm(request.POST or None)
    if form.is_valid():
        Comment.objects.create(
            post=post,
            author=request.user,
            text=form.cleaned_data['text'],
        )
    return redirect('blog:post_detail', pk=post.pk)


@login_required
def edit_comment(request, post_id, comment_id):
    post = _get_post_for_comment_or_404(request=request, post_id=post_id)
    comment = get_object_or_404(Comment, pk=comment_id, post=post)
    if comment.author != request.user:
        raise PermissionDenied

    form = CommentForm(request.POST or None, instance=comment)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('blog:post_detail', pk=post.pk)

    return render(
        request,
        'blog/comment.html',
        {'form': form, 'comment': comment},
    )


@login_required
def delete_comment(request, post_id, comment_id):
    post = _get_post_for_comment_or_404(request=request, post_id=post_id)
    comment = get_object_or_404(Comment, pk=comment_id, post=post)
    if comment.author != request.user:
        raise PermissionDenied

    if request.method == 'POST':
        comment.delete()
        return redirect('blog:post_detail', pk=post.pk)

    return render(request, 'blog/comment.html', {'comment': comment})


class CommentDeleteView(LoginRequiredMixin, DeleteView):
    model = Comment
    template_name = 'blog/comment.html'
    context_object_name = 'comment'
    pk_url_kwarg = 'comment_id'

    def get_queryset(self):
        return Comment.objects.select_related('author', 'post')

    def dispatch(self, request, *args, **kwargs):
        post = _get_post_for_comment_or_404(
            request=request,
            post_id=kwargs['post_id'],
        )
        self.comment_post = post
        comment = self.get_object()
        if comment.author != request.user:
            raise PermissionDenied
        if comment.post_id != post.id:
            raise Http404
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse('blog:post_detail', kwargs={'pk': self.comment_post.pk})

import json
import logging

from rest_framework import generics, permissions, status, exceptions
from django.db.models import Count
from django.http import StreamingHttpResponse
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Conversation, Message
from .serializers import ConversationSerializer, ConversationListSerializer, MessageSerializer
from .services import LLMUnavailableError, generate_assistant_reply, stream_assistant_reply
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiResponse

logger = logging.getLogger(__name__)


def _sse(event, payload):
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n"

class ConversationListView(generics.ListCreateAPIView):
    serializer_class = ConversationListSerializer
    permission_classes = (permissions.IsAuthenticated,)
    
    def get_queryset(self):
        return Conversation.objects.filter(user=self.request.user).annotate(message_count=Count('messages'))
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
    
    @extend_schema(
        summary="List all conversations",
        description="Retrieve all conversations for the authenticated user, ordered by most recent",
        tags=['Chat'],
        responses={
            200: OpenApiResponse(
                response=ConversationListSerializer(many=True),
                description="List of conversations retrieved successfully"
            ),
            401: OpenApiResponse(
                description="Authentication credentials not provided or invalid"
            ),
        },
        examples=[
            OpenApiExample(
                'Successful Response',
                value=[
                    {
                        'uuid': '3f7a2c1e-8b4d-4f0e-9a2c-1e8b4d4f0e9a',
                        'title': 'My First Conversation',
                        'created_at': '2026-03-03T10:00:00Z',
                        'updated_at': '2026-03-03T10:00:00Z',
                        'message_count': 0
                    }
                ],
                response_only=True,
            ),
        ]
    )
    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)
    
    @extend_schema(
        summary="Create a new conversation",
        description="Create a new conversation with the specified title",
        tags=['Chat'],
        request=ConversationSerializer,
        responses={
            201: OpenApiResponse(
                response=ConversationListSerializer,
                description="Conversation created successfully"
            ),
            400: OpenApiResponse(
                description="Invalid data provided (e.g., missing title)"
            ),
            401: OpenApiResponse(
                description="Authentication required"
            ),
        },
        examples=[
            OpenApiExample(
                'Create Request',
                value={
                    'title': 'My New Conversation'
                },
                request_only=True,
            ),
            OpenApiExample(
                'Create Response',
                value={
                    'uuid': '3f7a2c1e-8b4d-4f0e-9a2c-1e8b4d4f0e9a',
                    'title': 'My New Conversation',
                    'created_at': '2026-03-03T10:00:00Z',
                    'updated_at': '2026-03-03T10:00:00Z',
                    'message_count': 0
                },
                response_only=True,
            ),
        ]
    )
    def post(self, request, *args, **kwargs):
        return self.create(request, *args, **kwargs)

class ConversationDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ConversationSerializer
    lookup_field = 'uuid'
    http_method_names = ('get', 'patch', 'delete', 'head', 'options')
    permission_classes = (permissions.IsAuthenticated,)
    
    def get_queryset(self):
        return Conversation.objects.filter(user=self.request.user).annotate(message_count=Count('messages'))
    
    @extend_schema(
        summary="Get conversation details",
        description="Retrieve a specific conversation with all its messages",
        tags=['Chat'],
        responses={
            200: OpenApiResponse(
                response=ConversationSerializer,
                description="Conversation details retrieved successfully"
            ),
            401: OpenApiResponse(
                description="Authentication required"
            ),
            403: OpenApiResponse(
                description="You don't have permission to access this conversation"
            ),
            404: OpenApiResponse(
                description="Conversation not found"
            ),
        },
        examples=[
            OpenApiExample(
                'Successful Response',
                value={
                    'uuid': '3f7a2c1e-8b4d-4f0e-9a2c-1e8b4d4f0e9a',
                    'title': 'My First Conversation',
                    'created_at': '2026-03-03T10:00:00Z',
                    'updated_at': '2026-03-03T10:06:00Z',
                    'message_count': 2,
                    'messages': [
                        {
                            'uuid': '5e4b3a2c-1d9f-4b8e-a3c5-6d7f8a9b0c1d',
                            'role': 'user',
                            'content': 'What is Django?',
                            'created_at': '2026-03-03T10:04:00Z'
                        },
                        {
                            'uuid': 'a1b2c3d4-5e6f-4a7b-8c9d-0e1f2a3b4c5d',
                            'role': 'assistant',
                            'content': 'Django is a Python web framework...',
                            'created_at': '2026-03-03T10:04:01Z'
                        }
                    ]
                },
                response_only=True,
            ),
        ]
    )
    def get(self, request, *args, **kwargs):
        return self.retrieve(request, *args, **kwargs)
    
    @extend_schema(
        summary="Delete conversation",
        description="Delete a conversation and all its messages",
        tags=['Chat'],
        responses={
            204: OpenApiResponse(
                description="Conversation deleted successfully"
            ),
            401: OpenApiResponse(
                description="Authentication required"
            ),
            403: OpenApiResponse(
                description="Permission denied"
            ),
            404: OpenApiResponse(
                description="Conversation not found"
            ),
        }
    )
    def delete(self, request, *args, **kwargs):
        return self.destroy(request, *args, **kwargs)
    
    @extend_schema(
        summary="Partially update conversation",
        description="Partially update a conversation title (PATCH)",
        tags=['Chat'],
        request=ConversationSerializer,
        responses={
            200: ConversationSerializer,
            400: OpenApiResponse(description="Invalid data"),
            401: OpenApiResponse(description="Authentication required"),
            403: OpenApiResponse(description="Permission denied"),
            404: OpenApiResponse(description="Conversation not found"),
        },
        examples=[
            OpenApiExample(
                'Partial Update Request',
                value={
                    'title': 'New Title Only'
                },
                request_only=True,
            ),
        ]
    )
    def patch(self, request, *args, **kwargs):
        return self.partial_update(request, *args, **kwargs)

class MessageListCreateView(generics.ListCreateAPIView):
    serializer_class = MessageSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def _get_owned_conversation(self):
        conversation = Conversation.objects.filter(
            uuid=self.kwargs['conversation_id'],
            user=self.request.user,
        ).first()
        if conversation is None:
            raise exceptions.NotFound('Conversation not found')
        return conversation

    def get_queryset(self):
        return Message.objects.filter(conversation=self._get_owned_conversation()).order_by('created_at')

    @extend_schema(
        summary="List messages of a conversation",
        description="Retrieve all messages of a conversation owned by the authenticated user",
        tags=['Chat'],
        responses={
            200: OpenApiResponse(
                response=MessageSerializer(many=True),
                description="Messages of the conversation"
            ),
            401: OpenApiResponse(description="Authentication required"),
            404: OpenApiResponse(description="Conversation not found or not owned by the caller"),
        },
    )
    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)

    @extend_schema(
        summary="Send a message in a conversation",
        description="Send a message inside an existing conversation and return the complete assistant message",
        tags=['Chat'],
        request=OpenApiExample(
            'Message Request',
            value={'message': 'What is the capital of France?'},
        ),
        responses={
            201: OpenApiResponse(
                response=MessageSerializer,
                description="Assistant message created"
            ),
            400: OpenApiResponse(description="Message field is required"),
            401: OpenApiResponse(description="Authentication required"),
            404: OpenApiResponse(description="Conversation not found or not owned by the caller"),
            503: OpenApiResponse(description="The AI provider is unavailable"),
        },
    )
    def post(self, request, *args, **kwargs):
        user_message = request.data.get('message')
        if not user_message:
            raise exceptions.ValidationError('Message is required')
        conversation = self._get_owned_conversation()
        try:
            ai_msg = generate_assistant_reply(conversation, user_message)
        except LLMUnavailableError as e:
            headers = {}
            if e.retry_after:
                headers['Retry-After'] = str(e.retry_after)
            return Response(
                {'error': {'code': 'llm_unavailable', 'message': str(e), 'details': {}}},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
                headers=headers,
            )
        except Exception as e:
            logger.error(f"Chat error for user {request.user.id}: {str(e)}")
            raise
        return Response(MessageSerializer(ai_msg).data, status=status.HTTP_201_CREATED)


class MessageStreamView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def _get_owned_conversation(self):
        conversation = Conversation.objects.filter(
            uuid=self.kwargs['conversation_id'],
            user=self.request.user,
        ).first()
        if conversation is None:
            raise exceptions.NotFound('Conversation not found')
        return conversation

    @extend_schema(
        summary="Stream a message in a conversation",
        description=(
            "Send a message inside an existing conversation and stream the assistant reply as "
            "Server-Sent Events (`text/event-stream`). Emits `token` events with the reply "
            "fragments, then a `done` event carrying the message and conversation ids, or an "
            "`error` event in the contract error format."
        ),
        tags=['Chat'],
        request=OpenApiExample(
            'Message Request',
            value={'message': 'What is the capital of France?'},
        ),
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.STR,
                description="SSE stream: `token`, then `done`, or an `error` event",
            ),
            400: OpenApiResponse(description="Message field is required"),
            401: OpenApiResponse(description="Authentication required"),
            404: OpenApiResponse(description="Conversation not found or not owned by the caller"),
        },
    )
    def post(self, request, *args, **kwargs):
        user_message = request.data.get('message')
        if not user_message:
            raise exceptions.ValidationError('Message is required')
        conversation = self._get_owned_conversation()

        def event_stream():
            state = {}
            stream = stream_assistant_reply(conversation, user_message, state)
            try:
                for fragment in stream:
                    yield _sse('token', {'content': fragment})
                assistant = state['assistant_message']
                yield _sse('done', {
                    'message_id': str(assistant.uuid),
                    'conversation_id': str(conversation.uuid),
                })
            except LLMUnavailableError as e:
                yield _sse('error', {'code': 'llm_unavailable', 'message': str(e)})
            except Exception:
                logger.error(
                    'Streaming error for conversation %s', conversation.uuid, exc_info=True
                )
                yield _sse('error', {
                    'code': 'server_error',
                    'message': 'An unexpected error occurred.',
                })
            finally:
                stream.close()

        response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response
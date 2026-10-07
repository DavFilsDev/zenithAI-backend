from rest_framework import generics, permissions, status, exceptions
from django.db.models import Count
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Conversation, Message
from .serializers import ConversationSerializer, ConversationListSerializer, MessageSerializer
from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiResponse
from .services import gemini_service, LLMUnavailableError
import logging

logger = logging.getLogger(__name__)

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
    permission_classes = (permissions.IsAuthenticated,)
    
    def get_queryset(self):
        return Conversation.objects.filter(user=self.request.user)
    
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
        summary="Update conversation",
        description="Update the title of a conversation",
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
                'Update Request',
                value={
                    'title': 'Updated Conversation Title'
                },
                request_only=True,
            ),
        ]
    )
    def put(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)
    
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

class ChatView(APIView):
    permission_classes = (permissions.IsAuthenticated,)
    
    @extend_schema(
        summary="Send a message to the AI",
        description="""
        Send a message to the AI and receive a response using Google Gemini.
        
        **If conversation_id is provided:**
        - Continues an existing conversation
        - Message is added to that conversation's history
        
        **If no conversation_id:**
        - Creates a new conversation
        - Uses the first 50 characters of your message as the title
        - Returns the AI response with the new conversation context
        
        The AI uses Google Gemini 2.5 Flash for fast, intelligent responses.
        """,
        tags=['Chat'],
        request=OpenApiExample(
            'Message Request',
            value={
                'message': 'What is the capital of France?',
            },
            description='JSON object containing the user message',
        ),
        responses={
            200: OpenApiResponse(
                response=MessageSerializer,
                description='AI response message from Gemini',
                examples=[
                    OpenApiExample(
                        'Successful Response',
                        value={
                            'uuid': 'a1b2c3d4-5e6f-4a7b-8c9d-0e1f2a3b4c5d',
                            'role': 'assistant',
                            'content': 'The capital of France is Paris. It is known as the "City of Light" and is famous for the Eiffel Tower, Louvre Museum, and Notre-Dame Cathedral.',
                            'created_at': '2026-03-03T10:30:00Z'
                        }
                    )
                ]
            ),
            201: OpenApiResponse(
                description='New conversation created with AI response',
                response=MessageSerializer,
            ),
            400: OpenApiResponse(
                description='Bad request - message field is required',
                examples=[
                    OpenApiExample(
                        'Missing Message',
                        value={'error': {'code': 'validation_error', 'message': 'Message is required', 'details': {}}}
                    )
                ]
            ),
            401: OpenApiResponse(
                description='Authentication credentials not provided',
            ),
            404: OpenApiResponse(
                description='Conversation not found or does not belong to user',
                examples=[
                    OpenApiExample(
                        'Conversation Not Found',
                        value={'error': {'code': 'not_found', 'message': 'Conversation not found', 'details': {}}}
                    )
                ]
            ),
            503: OpenApiResponse(
                description='The AI provider is unavailable',
                examples=[
                    OpenApiExample(
                        'Provider Unavailable',
                        value={'error': {'code': 'llm_unavailable', 'message': 'The AI service is temporarily unavailable. Please try again later.', 'details': {}}}
                    )
                ]
            ),
            500: OpenApiResponse(
                description='Internal server error not related to the provider',
                examples=[
                    OpenApiExample(
                        'Server Error',
                        value={'error': {'code': 'server_error', 'message': 'An unexpected error occurred.', 'details': {}}}
                    )
                ]
            ),
        },
        examples=[
            OpenApiExample(
                'New Conversation',
                summary='Start a new conversation',
                description='Send message without conversation_id to create new chat',
                value={'message': 'Hello, who are you?'},
                request_only=True,
            ),
            OpenApiExample(
                'Continue Conversation',
                summary='Continue existing conversation',
                description='Include conversation_id to add to existing chat',
                value={'message': 'Tell me more about that'},
                request_only=True,
            ),
        ]
    )
    def post(self, request, conversation_id=None):
        user_message = request.data.get('message')
        if not user_message:
            raise exceptions.ValidationError('Message is required')
        
        if conversation_id:
            conversation = Conversation.objects.filter(
                uuid=conversation_id, 
                user=request.user
            ).first()
            if not conversation:
                raise exceptions.NotFound('Conversation not found')
        else:
            # Create new conversation with first message as title
            title = user_message[:50] + "..." if len(user_message) > 50 else user_message
            conversation = Conversation.objects.create(
                user=request.user,
                title=title
            )
        
        user_msg = Message.objects.create(
            conversation=conversation,
            role='user',
            content=user_message
        )
        
        try:
            # Conversation history, excluding the message just saved
            messages = Message.objects.filter(conversation=conversation).order_by('created_at')
            chat_history = [{'role': msg.role, 'content': msg.content} for msg in messages if msg.id != user_msg.id]
            
            ai_response = gemini_service.generate_response(user_message, chat_history)
            
            ai_msg = Message.objects.create(
                conversation=conversation,
                role='assistant',
                content=ai_response
            )
            
            serializer = MessageSerializer(ai_msg)
            
            # Return 201 if new conversation was created, 200 otherwise
            status_code = status.HTTP_201_CREATED if not conversation_id else status.HTTP_200_OK
            return Response(serializer.data, status=status_code)

        except LLMUnavailableError as e:
            return Response(
                {'error': {'code': 'llm_unavailable', 'message': str(e), 'details': {}}},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.error(f"Chat error for user {request.user.id}: {str(e)}")
            raise
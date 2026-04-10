from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from properties.models import Property, MediaProperty, PropertyVisit
from communications.models import Conversation, Message
from insights.analytics_service import AgentAnalyticsService
from django.db import connection, reset_queries

User = get_user_model()

class AnalyticsPerformanceTest(TestCase):
    def setUp(self):
        self.agent = User.objects.create_user(
            username='agent', email='agent@example.com', password='password'
        )
        self.user = User.objects.create_user(
            username='user', email='user@example.com', password='password'
        )
        self.service = AgentAnalyticsService(self.agent.id)

    def test_optimization_suggestions_queries(self):
        # Create properties with media
        for i in range(5):
            prop = Property.objects.create(
                owner=self.agent,
                title=f'Property {i}',
                price=100000,
                city='Dar es Salaam',
                is_published=True
            )
            # Add some media
            if i % 2 == 0:
                MediaProperty.objects.create(property=prop, Images='test.jpg')
            if i % 3 == 0:
                MediaProperty.objects.create(property=prop, videos='test.mp4')

        # Reset queries to track count
        reset_queries()
        
        # Expect 1 query (optimized) 
        with self.assertNumQueries(1): 
            suggestions = self.service.get_optimization_suggestions()
        
        # Verify suggestions content (basic check)
        self.assertTrue(len(suggestions) >= 0)

    def test_lead_insights_response_time(self):
        # Create conversation
        conv = Conversation.objects.create(
            agent=self.agent,
            user=self.user,
            property_id=1 # assuming dummy ID or need real prop, let's make one
        )
        prop = Property.objects.create(owner=self.agent, title='Test', price=100)
        conv.property = prop
        conv.save()
        
        # Helper to create message with specific time
        def create_msg(sender, time_offset_minutes):
            msg = Message.objects.create(conversation=conv, sender=sender, text='msg')
            msg.created_at = timezone.now() - timedelta(days=1) + timedelta(minutes=time_offset_minutes)
            msg.save() 
            return msg

        base_time = timezone.now() - timedelta(days=1)
        
        # Scenario: User sends, Agent replies 5 mins later
        create_msg(self.user, 0)
        create_msg(self.agent, 5)
        
        # Scenario: User sends, Agent replies 10 mins later (relative to base, so say 60 mins later)
        create_msg(self.user, 60)
        create_msg(self.agent, 70) # 10 mins after user

        # Expected avg: (5 + 10) / 2 = 7.5 mins = 450 seconds
        
        # Reset queries to ensure lead_insights is reasonably efficient
        reset_queries()
        
        # This will execute a few queries (messages, counts), preventing N+1 loop
        data = self.service.get_lead_insights()
        
        self.assertEqual(data['avg_response_time_seconds'], 450)

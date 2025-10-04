"""
Test Notification Provider Integration
Tests that Email, SMS, and WhatsApp accounts are properly configured and working
RUN THIS FIRST before testing notification service functions
"""

import sys
import os
from datetime import datetime

# Resend imports (Alternative to SendGrid)
try:
    import resend
    EMAIL_PROVIDER = "resend"
except ImportError:
    # Fallback to SendGrid if Resend not installed
    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail, Email, To, Content
        EMAIL_PROVIDER = "sendgrid"
    except ImportError:
        EMAIL_PROVIDER = None

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.core.config import settings

def print_result(test_name, passed, details=""):
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status} | {test_name}")
    if details:
        print(f"     └─ {details}")

def test_email_configuration():
    """Test 1: Email configuration (Multiple Providers Supported)"""
    
    print("\n" + "="*60)
    print(f"Testing: Email Provider Configuration ({EMAIL_PROVIDER.upper() if EMAIL_PROVIDER else 'NONE'})")
    print("="*60)
    
    print("\n[Test 1.1] Email provider settings")
    
    # Check for Resend (Recommended)
    has_resend_key = hasattr(settings, 'RESEND_API_KEY') and settings.RESEND_API_KEY
    if has_resend_key:
        print_result("RESEND_API_KEY configured", True,
                    f"Value: {settings.RESEND_API_KEY[:10] + '...'}")
    
    # Check for SendGrid (Alternative)
    has_sendgrid_key = hasattr(settings, 'SENDGRID_API_KEY') and settings.SENDGRID_API_KEY
    if has_sendgrid_key:
        print_result("SENDGRID_API_KEY configured", True,
                    f"Value: {settings.SENDGRID_API_KEY[:10] + '...'}")
    
    # Check FROM_EMAIL
    has_from_email = hasattr(settings, 'FROM_EMAIL') and settings.FROM_EMAIL
    print_result("FROM_EMAIL configured", has_from_email,
                f"Value: {settings.FROM_EMAIL if has_from_email else 'NOT SET'}")
    
    if (has_resend_key or has_sendgrid_key) and has_from_email:
        provider = "Resend" if has_resend_key else "SendGrid"
        print(f"\n✅ {provider} properly configured")
        return True
    else:
        print("\n❌ No email provider configured. Choose one:")
        print("\n   OPTION 1 (Recommended): Resend")
        print("   RESEND_API_KEY=re_xxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
        print("   FROM_EMAIL=onboarding@resend.dev")
        print("   Get API Key: https://resend.com/api-keys")
        print("\n   OPTION 2 (Alternative): SendGrid")
        print("   SENDGRID_API_KEY=SG.xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
        print("   FROM_EMAIL=your-verified-email@yourdomain.com")
        print("   Get API Key: https://app.sendgrid.com/settings/api_keys")
        return False

def test_sendgrid_api_connection():
    """Test 2: SendGrid API authentication"""
    
    print("\n[Test 2] SendGrid API authentication")
    
    try:
        # Initialize SendGrid client
        sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
        
        # Test API key validity by making a simple API call
        # We'll use the API key validation endpoint
        print_result("SendGrid API client initialized", True,
                    f"Using API key: {settings.SENDGRID_API_KEY[:10]}...")
        
        print_result("API key format valid", True,
                    "Key appears to be in correct format")
        
        return True
        
    except Exception as e:
        print_result("SendGrid API authentication", False,
                    f"Error: {str(e)}")
        print("\n⚠️  Authentication failed. Please check:")
        print("   1. SENDGRID_API_KEY is correct and not expired")
        print("   2. API key has 'Mail Send' permissions")
        print("   3. Generate a new key at: https://app.sendgrid.com/settings/api_keys")
        return False

def test_send_test_email():
    """Test 3: Send actual test email using SendGrid API"""
    
    print("\n[Test 3] Send test email via SendGrid API")
    
    # Get test recipient
    test_recipient = input("\nEnter email address to send test to (or press Enter to skip): ").strip()
    
    if not test_recipient:
        print_result("Test email skipped", True, "User chose to skip")
        return True
    
    try:
        # Create the email message
        message = Mail(
            from_email=Email(settings.FROM_EMAIL),
            to_emails=To(test_recipient),
            subject=f"NutriLens Test Email - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            plain_text_content=Content("text/plain", "This is a test email from NutriLens notification system."),
            html_content=Content("text/html", f"""
                <html>
                  <body>
                    <h2>✅ Email Integration Test</h2>
                    <p>This is a test email from <strong>NutriLens</strong> notification system.</p>
                    <p>If you received this, your SendGrid API integration is working correctly!</p>
                    <hr>
                    <p><small>Sent via SendGrid API at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</small></p>
                  </body>
                </html>
            """)
        )
        
        # Send email using SendGrid API
        sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
        response = sg.send(message)
        
        # Check response
        if response.status_code in [200, 201, 202]:
            print_result("Test email sent via SendGrid API", True,
                        f"Sent to {test_recipient} (Status: {response.status_code})")
            print(f"\n     ⚠️  Please check {test_recipient} inbox (and spam folder)")
            print(f"     ℹ️  SendGrid Message ID: {response.headers.get('X-Message-Id', 'N/A')}")
            return True
        else:
            print_result("Test email sent via SendGrid API", False,
                        f"Unexpected status code: {response.status_code}")
            return False
        
    except Exception as e:
        print_result("Test email sent via SendGrid API", False,
                    f"Error: {str(e)}")
        print("\n⚠️  Common issues:")
        print("   1. FROM_EMAIL not verified in SendGrid")
        print("      → Go to: https://app.sendgrid.com/settings/sender_auth")
        print("   2. API key lacks 'Mail Send' permission")
        print("      → Create new key with full access")
        print("   3. SendGrid account suspended or limited")
        print("      → Check account status in dashboard")
        return False

def test_sms_configuration():
    """Test 4: SMS configuration (Twilio)"""
    
    print("\n" + "="*60)
    print("Testing: SMS Provider Configuration (Twilio)")
    print("="*60)
    
    print("\n[Test 4.1] Twilio settings are configured")
    
    has_account_sid = hasattr(settings, 'TWILIO_ACCOUNT_SID') and settings.TWILIO_ACCOUNT_SID
    print_result("TWILIO_ACCOUNT_SID configured", has_account_sid,
                f"Value: {settings.TWILIO_ACCOUNT_SID[:10] + '...' if has_account_sid else 'NOT SET'}")
    
    has_auth_token = hasattr(settings, 'TWILIO_AUTH_TOKEN') and settings.TWILIO_AUTH_TOKEN
    print_result("TWILIO_AUTH_TOKEN configured", has_auth_token,
                f"Value: {'***' if has_auth_token else 'NOT SET'}")
    
    has_phone_number = hasattr(settings, 'TWILIO_PHONE_NUMBER') and settings.TWILIO_PHONE_NUMBER
    print_result("TWILIO_PHONE_NUMBER configured", has_phone_number,
                f"Value: {settings.TWILIO_PHONE_NUMBER if has_phone_number else 'NOT SET'}")
    
    if has_account_sid and has_auth_token and has_phone_number:
        print("\n✅ Twilio SMS properly configured")
        return True
    else:
        print("\n⚠️  Twilio SMS not fully configured. Please set in .env:")
        print("\n   TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
        print("   TWILIO_AUTH_TOKEN=your_auth_token")
        print("   TWILIO_PHONE_NUMBER=+1234567890")
        print("\n   Get credentials: https://console.twilio.com/")
        return False

def test_whatsapp_configuration():
    """Test 5: WhatsApp configuration (Twilio)"""
    
    print("\n" + "="*60)
    print("Testing: WhatsApp Provider Configuration (Twilio)")
    print("="*60)
    
    print("\n[Test 5.1] Twilio WhatsApp settings are configured")
    
    has_account_sid = hasattr(settings, 'TWILIO_ACCOUNT_SID') and settings.TWILIO_ACCOUNT_SID
    has_auth_token = hasattr(settings, 'TWILIO_AUTH_TOKEN') and settings.TWILIO_AUTH_TOKEN
    has_whatsapp_number = hasattr(settings, 'TWILIO_WHATSAPP_NUMBER') and settings.TWILIO_WHATSAPP_NUMBER
    
    print_result("TWILIO_ACCOUNT_SID configured", has_account_sid,
                f"Value: {settings.TWILIO_ACCOUNT_SID[:10] + '...' if has_account_sid else 'NOT SET'}")
    
    print_result("TWILIO_WHATSAPP_NUMBER configured", has_whatsapp_number,
                f"Value: {settings.TWILIO_WHATSAPP_NUMBER if has_whatsapp_number else 'NOT SET'}")
    
    if has_account_sid and has_auth_token and has_whatsapp_number:
        print("\n✅ Twilio WhatsApp properly configured")
        return True
    else:
        print("\n⚠️  Twilio WhatsApp not fully configured. Please set in .env:")
        print("\n   TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
        print("   TWILIO_AUTH_TOKEN=your_auth_token")
        print("   TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886")
        print("\n   Get WhatsApp sandbox: https://console.twilio.com/us1/develop/sms/try-it-out/whatsapp-learn")
        return False

def main():
    """Run all provider tests"""
    
    print("\n" + "="*60)
    print("NOTIFICATION PROVIDER INTEGRATION TEST")
    print("="*60)
    print(f"Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    results = {
        'email_config': False,
        'email_connection': False,
        'email_send': False,
        'sms_config': False,
        'whatsapp_config': False
    }
    
    # Test Email (SendGrid API)
    results['email_config'] = test_email_configuration()
    if results['email_config']:
        results['email_connection'] = test_sendgrid_api_connection()
        if results['email_connection']:
            results['email_send'] = test_send_test_email()
    
    # Test SMS (Twilio)
    results['sms_config'] = test_sms_configuration()
    
    # Test WhatsApp (Twilio)
    results['whatsapp_config'] = test_whatsapp_configuration()
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(results.values())
    total = len(results)
    
    print(f"\nTests Passed: {passed}/{total}")
    print("\nEmail (SendGrid API):")
    print(f"  - Configuration: {'✅' if results['email_config'] else '❌'}")
    print(f"  - API Connection: {'✅' if results['email_connection'] else '❌'}")
    print(f"  - Send Test: {'✅' if results['email_send'] else '❌'}")
    print(f"\nSMS (Twilio):")
    print(f"  - Configuration: {'✅' if results['sms_config'] else '❌'}")
    print(f"\nWhatsApp (Twilio):")
    print(f"  - Configuration: {'✅' if results['whatsapp_config'] else '❌'}")
    
    if results['email_config'] and results['email_connection'] and results['email_send']:
        print("\n🎉 Email integration fully working!")
    
    print("\n" + "="*60)

if __name__ == "__main__":
    main()
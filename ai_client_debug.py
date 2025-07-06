#!/usr/bin/env python3
"""
Test script for dynamic interaction with VertexClient
This script provides various testing scenarios for the AI client
"""

import logging
import datetime
import sys
import json
from typing import List, Dict, Any
import config
from utils.ai_client import VertexClient
from utils.custom_types import ChatMessage

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


class VertexClientTester:
    """Dynamic tester for VertexClient functionality"""

    def __init__(self):
        """Initialize the tester"""
        self.ai_client = None
        self.test_results = {}

    def initialize_client(self) -> bool:
        """Initialize the VertexClient"""
        print("\n" + "=" * 60)
        print("🚀 INITIALIZING VERTEX CLIENT")
        print("=" * 60)

        try:
            self.ai_client = VertexClient(
                config_path=config.MODELS_CONFIG_PATH,
                project_id=config.VERTEX_PROJECT_ID,
                default_region=config.VERTEX_REGION,
                auto_initialize=True,
            )
            print("✅ AI client initialized successfully")
            self.test_results["initialization"] = {"status": "success", "error": None}
            return True

        except Exception as e:
            print(f"❌ Failed to initialize AI client: {e}")
            self.test_results["initialization"] = {"status": "failed", "error": str(e)}
            return False

    def test_health_check(self) -> Dict[str, Any]:
        """Test the health check functionality"""
        print("\n" + "=" * 60)
        print("🏥 TESTING HEALTH CHECK")
        print("=" * 60)

        if not self.ai_client:
            print("❌ AI client not initialized")
            return {"status": "skipped", "reason": "client_not_initialized"}

        try:
            health = self.ai_client.health_check()
            print("📊 Health Check Results:")
            for key, value in health.items():
                print(f"   {key}: {value}")

            self.test_results["health_check"] = health
            if health.get("status") == "healthy":
                print("✅ Health check passed")
            else:
                print(
                    f"⚠️  Health check warning: {health.get('error', 'Unknown issue')}"
                )

            return health

        except Exception as e:
            print(f"❌ Health check failed: {e}")
            result = {"status": "error", "error": str(e)}
            self.test_results["health_check"] = result
            return result

    def test_model_info(self) -> Dict[str, Any]:
        """Test model information retrieval"""
        print("\n" + "=" * 60)
        print("📋 TESTING MODEL INFORMATION")
        print("=" * 60)

        if not self.ai_client:
            print("❌ AI client not initialized")
            return {"status": "skipped", "reason": "client_not_initialized"}

        try:
            # List available models
            models = self.ai_client.list_models()
            print(f"📝 Available models: {models}")

            model_details = {}
            for model_id in models:
                info = self.ai_client.get_model_info(model_id)
                model_details[model_id] = info
                print(f"\n🤖 Model: {model_id}")
                if info:
                    for key, value in info.items():
                        print(f"   {key}: {value}")
                else:
                    print("   ❌ No information available")

            self.test_results["model_info"] = {
                "models": models,
                "details": model_details,
                "status": "success",
            }

            return model_details

        except Exception as e:
            print(f"❌ Model info test failed: {e}")
            result = {"status": "error", "error": str(e)}
            self.test_results["model_info"] = result
            return result

    def test_simple_prediction(self) -> Dict[str, Any]:
        """Test simple prediction functionality"""
        print("\n" + "=" * 60)
        print("🧠 TESTING SIMPLE PREDICTION")
        print("=" * 60)

        if not self.ai_client:
            print("❌ AI client not initialized")
            return {"status": "skipped", "reason": "client_not_initialized"}

        try:
            # Simple test conversation
            test_messages: List[ChatMessage] = [
                {"role": "user", "content": "Hello! Can you tell me what 2+2 equals?"}
            ]

            print("📤 Sending test message:")
            print(f"   User: {test_messages[0]['content']}")

            result = self.ai_client.predict(test_messages, max_tokens=100)

            if result and result.get("success"):
                generated_text = result.get("generated_text", "No response")
                print(f"📥 AI Response: {generated_text}")
                print(f"🤖 Model used: {result.get('model_id', 'unknown')}")
                print(f"⏱️  Timestamp: {result.get('timestamp', 'unknown')}")

                self.test_results["simple_prediction"] = {
                    "status": "success",
                    "response": generated_text,
                    "model_id": result.get("model_id"),
                    "full_result": result,
                }

            else:
                error_msg = (
                    result.get("error", "Unknown error") if result else "No result"
                )
                print(f"❌ Prediction failed: {error_msg}")
                self.test_results["simple_prediction"] = {
                    "status": "failed",
                    "error": error_msg,
                    "full_result": result,
                }

            return result

        except Exception as e:
            print(f"❌ Simple prediction test failed: {e}")
            result = {"status": "error", "error": str(e)}
            self.test_results["simple_prediction"] = result
            return result

    def test_conversation_flow(self) -> Dict[str, Any]:
        """Test multi-turn conversation"""
        print("\n" + "=" * 60)
        print("💬 TESTING CONVERSATION FLOW")
        print("=" * 60)

        if not self.ai_client:
            print("❌ AI client not initialized")
            return {"status": "skipped", "reason": "client_not_initialized"}

        try:
            # Multi-turn conversation
            conversation: List[ChatMessage] = [
                {
                    "role": "user",
                    "content": "I'm feeling anxious about an upcoming presentation.",
                },
                {
                    "role": "assistant",
                    "content": "I understand that presentations can cause anxiety. Can you tell me more about what specifically worries you about this presentation?",
                },
                {
                    "role": "user",
                    "content": "I'm worried I'll forget what to say and embarrass myself in front of my colleagues.",
                },
            ]

            print("📤 Testing conversation flow:")
            for i, msg in enumerate(conversation, 1):
                role_emoji = "👤" if msg["role"] == "user" else "🤖"
                print(f"   {i}. {role_emoji} {msg['role'].title()}: {msg['content']}")

            print("\n📤 Sending conversation for AI response...")

            result = self.ai_client.predict(
                conversation, max_tokens=200, temperature=0.7
            )

            if result and result.get("success"):
                generated_text = result.get("generated_text", "No response")
                print(f"\n📥 AI Response: {generated_text}")
                print(f"🤖 Model used: {result.get('model_id', 'unknown')}")
                print(
                    f"📊 Messages processed: {result.get('messages_count', 'unknown')}"
                )

                self.test_results["conversation_flow"] = {
                    "status": "success",
                    "response": generated_text,
                    "messages_count": result.get("messages_count"),
                    "full_result": result,
                }

            else:
                error_msg = (
                    result.get("error", "Unknown error") if result else "No result"
                )
                print(f"❌ Conversation test failed: {error_msg}")
                self.test_results["conversation_flow"] = {
                    "status": "failed",
                    "error": error_msg,
                    "full_result": result,
                }

            return result

        except Exception as e:
            print(f"❌ Conversation flow test failed: {e}")
            result = {"status": "error", "error": str(e)}
            self.test_results["conversation_flow"] = result
            return result

    def test_edge_cases(self) -> Dict[str, Any]:
        """Test edge cases and error handling"""
        print("\n" + "=" * 60)
        print("⚡ TESTING EDGE CASES")
        print("=" * 60)

        if not self.ai_client:
            print("❌ AI client not initialized")
            return {"status": "skipped", "reason": "client_not_initialized"}

        edge_case_results = {}

        # Test 1: Empty message
        print("\n🧪 Test 1: Empty message")
        try:
            empty_result = self.ai_client.predict([], max_tokens=50)
            print(
                f"   Result: {empty_result.get('success') if empty_result else 'None'}"
            )
            edge_case_results["empty_message"] = empty_result
        except Exception as e:
            print(f"   Exception: {e}")
            edge_case_results["empty_message"] = {"error": str(e)}

        # Test 2: Very long message
        print("\n🧪 Test 2: Very long message")
        try:
            long_content = "This is a very long message. " * 100
            long_messages = [{"role": "user", "content": long_content}]
            long_result = self.ai_client.predict(long_messages, max_tokens=50)
            print(f"   Result: {long_result.get('success') if long_result else 'None'}")
            edge_case_results["long_message"] = long_result
        except Exception as e:
            print(f"   Exception: {e}")
            edge_case_results["long_message"] = {"error": str(e)}

        # Test 3: Invalid model ID
        print("\n🧪 Test 3: Invalid model ID")
        try:
            invalid_result = self.ai_client.predict(
                [{"role": "user", "content": "Test"}], model_id="invalid_model_id"
            )
            print(
                f"   Result: {invalid_result.get('success') if invalid_result else 'None'}"
            )
            edge_case_results["invalid_model"] = invalid_result
        except Exception as e:
            print(f"   Exception: {e}")
            edge_case_results["invalid_model"] = {"error": str(e)}

        # Test 4: Special characters and emojis
        print("\n🧪 Test 4: Special characters and emojis")
        try:
            special_messages = [
                {
                    "role": "user",
                    "content": "Hello! 🌟 How are you? Special chars: áéíóú ñ @#$%^&*()",
                }
            ]
            special_result = self.ai_client.predict(special_messages, max_tokens=50)
            print(
                f"   Result: {special_result.get('success') if special_result else 'None'}"
            )
            edge_case_results["special_chars"] = special_result
        except Exception as e:
            print(f"   Exception: {e}")
            edge_case_results["special_chars"] = {"error": str(e)}

        self.test_results["edge_cases"] = edge_case_results
        return edge_case_results

    def test_performance(self) -> Dict[str, Any]:
        """Test performance with multiple requests"""
        print("\n" + "=" * 60)
        print("🏃 TESTING PERFORMANCE")
        print("=" * 60)

        if not self.ai_client:
            print("❌ AI client not initialized")
            return {"status": "skipped", "reason": "client_not_initialized"}

        try:
            import time

            test_messages = [
                {"role": "user", "content": "What is artificial intelligence?"}
            ]

            print("📊 Running 3 consecutive requests...")
            times = []
            results = []

            for i in range(3):
                print(f"   Request {i+1}/3...", end=" ")
                start_time = time.time()

                result = self.ai_client.predict(test_messages, max_tokens=50)

                end_time = time.time()
                duration = end_time - start_time
                times.append(duration)
                results.append(result)

                success = result.get("success") if result else False
                print(f"{'✅' if success else '❌'} ({duration:.2f}s)")

            avg_time = sum(times) / len(times)
            print(f"\n📈 Performance Summary:")
            print(f"   Average response time: {avg_time:.2f}s")
            print(f"   Min response time: {min(times):.2f}s")
            print(f"   Max response time: {max(times):.2f}s")

            performance_result = {
                "status": "success",
                "avg_time": avg_time,
                "min_time": min(times),
                "max_time": max(times),
                "times": times,
                "results": results,
            }

            self.test_results["performance"] = performance_result
            return performance_result

        except Exception as e:
            print(f"❌ Performance test failed: {e}")
            result = {"status": "error", "error": str(e)}
            self.test_results["performance"] = result
            return result

    def generate_test_report(self) -> str:
        """Generate a comprehensive test report"""
        print("\n" + "=" * 60)
        print("📋 GENERATING TEST REPORT")
        print("=" * 60)

        report = {
            "test_session": {
                "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                "total_tests": len(self.test_results),
            },
            "results": self.test_results,
            "summary": {},
        }

        # Calculate summary
        passed = sum(
            1
            for r in self.test_results.values()
            if isinstance(r, dict) and r.get("status") in ["success", "healthy"]
        )
        failed = sum(
            1
            for r in self.test_results.values()
            if isinstance(r, dict)
            and r.get("status") in ["failed", "error", "unhealthy"]
        )
        skipped = sum(
            1
            for r in self.test_results.values()
            if isinstance(r, dict) and r.get("status") == "skipped"
        )

        report["summary"] = {
            "total_tests": len(self.test_results),
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "success_rate": (
                f"{(passed / len(self.test_results) * 100):.1f}%"
                if self.test_results
                else "0%"
            ),
        }

        print("📊 Test Summary:")
        print(f"   Total tests: {report['summary']['total_tests']}")
        print(f"   ✅ Passed: {report['summary']['passed']}")
        print(f"   ❌ Failed: {report['summary']['failed']}")
        print(f"   ⏭️  Skipped: {report['summary']['skipped']}")
        print(f"   📈 Success rate: {report['summary']['success_rate']}")

        # Save report to file
        report_filename = f"vertex_test_report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        try:
            with open(report_filename, "w") as f:
                json.dump(report, f, indent=2, default=str)
            print(f"\n💾 Report saved to: {report_filename}")
        except Exception as e:
            print(f"❌ Failed to save report: {e}")

        return report_filename

    def run_interactive_mode(self):
        """Run interactive mode for manual testing"""
        print("\n" + "=" * 60)
        print("🎮 INTERACTIVE MODE")
        print("=" * 60)
        print("Type your messages to chat with the AI")
        print(
            "Commands: 'quit' to exit, 'health' for health check, 'models' for model info"
        )

        if not self.ai_client:
            print("❌ AI client not initialized")
            return

        conversation_history = []

        while True:
            try:
                user_input = input("\n👤 You: ").strip()

                if user_input.lower() in ["quit", "exit", "q"]:
                    print("👋 Goodbye!")
                    break
                elif user_input.lower() == "health":
                    health = self.ai_client.health_check()
                    print(f"🏥 Health: {health}")
                    continue
                elif user_input.lower() == "models":
                    models = self.ai_client.list_models()
                    print(f"🤖 Models: {models}")
                    continue
                elif not user_input:
                    print("Please enter a message or command")
                    continue

                # Add user message to conversation
                conversation_history.append({"role": "user", "content": user_input})

                # Get AI response
                print("🤖 AI: Thinking...", end="", flush=True)
                result = self.ai_client.predict(
                    conversation_history, max_tokens=200, temperature=0.7
                )

                if result and result.get("success"):
                    ai_response = result.get("generated_text", "No response")
                    print(f"\r🤖 AI: {ai_response}")

                    # Add AI response to conversation
                    conversation_history.append(
                        {"role": "assistant", "content": ai_response}
                    )
                else:
                    error_msg = (
                        result.get("error", "Unknown error") if result else "No result"
                    )
                    print(f"\r❌ Error: {error_msg}")

            except KeyboardInterrupt:
                print("\n\n👋 Interrupted by user. Goodbye!")
                break
            except Exception as e:
                print(f"\n❌ Error in interactive mode: {e}")

    def run_all_tests(self) -> str:
        """Run all available tests"""
        print("🚀 STARTING COMPREHENSIVE VERTEX CLIENT TESTING")
        print("=" * 80)

        # Initialize client
        if not self.initialize_client():
            print("❌ Cannot proceed without AI client")
            return self.generate_test_report()

        # Run all tests
        self.test_health_check()
        self.test_model_info()
        self.test_simple_prediction()
        self.test_conversation_flow()
        self.test_edge_cases()
        self.test_performance()

        # Generate report
        return self.generate_test_report()


def main():
    """Main function to run the tester"""
    tester = VertexClientTester()

    print("🤖 Vertex Client Tester")
    print("Choose an option:")
    print("1. Run all tests")
    print("2. Interactive mode")
    print("3. Health check only")
    print("4. Custom test")

    try:
        choice = input("\nEnter your choice (1-4): ").strip()

        if choice == "1":
            tester.run_all_tests()
        elif choice == "2":
            if tester.initialize_client():
                tester.run_interactive_mode()
        elif choice == "3":
            if tester.initialize_client():
                tester.test_health_check()
        elif choice == "4":
            if tester.initialize_client():
                print("Available tests:")
                print("- health: Health check")
                print("- models: Model information")
                print("- simple: Simple prediction")
                print("- conversation: Conversation flow")
                print("- edge: Edge cases")
                print("- performance: Performance test")

                test_choice = input("Enter test name: ").strip().lower()

                if test_choice == "health":
                    tester.test_health_check()
                elif test_choice == "models":
                    tester.test_model_info()
                elif test_choice == "simple":
                    tester.test_simple_prediction()
                elif test_choice == "conversation":
                    tester.test_conversation_flow()
                elif test_choice == "edge":
                    tester.test_edge_cases()
                elif test_choice == "performance":
                    tester.test_performance()
                else:
                    print("Invalid test name")
        else:
            print("Invalid choice")

    except KeyboardInterrupt:
        print("\n\n👋 Testing interrupted by user")
    except Exception as e:
        print(f"\n❌ Error during testing: {e}")


if __name__ == "__main__":
    main()

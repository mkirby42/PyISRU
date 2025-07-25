import asyncio
import aiohttp
import time
from statistics import mean, median
import argparse

async def fetch_url(session, url, semaphore):
    """Fetch a single URL and return response time"""
    async with semaphore:
        start_time = time.time()
        try:
            async with session.get(url, timeout=10) as response:
                await response.text()
                return time.time() - start_time, response.status
        except Exception as e:
            return time.time() - start_time, 500

async def load_test(base_url, concurrent_users, total_requests):
    """Run load test with specified parameters"""
    
    # Test URLs (your main pages)
    test_urls = [
        f"{base_url}/",
        f"{base_url}/post/how_long_to_mars_base",
        f"{base_url}/post/a_the_other_the_unknown_and_ourselves", 
        f"{base_url}/post/personal_server",
        f"{base_url}/dashboard"
    ]
    
    semaphore = asyncio.Semaphore(concurrent_users)
    response_times = []
    status_codes = []
    
    print(f"Starting load test...")
    print(f"Target: {base_url}")
    print(f"Concurrent users: {concurrent_users}")
    print(f"Total requests: {total_requests}")
    print(f"Test URLs: {len(test_urls)}")
    print("-" * 50)
    
    start_time = time.time()
    
    async with aiohttp.ClientSession() as session:
        tasks = []
        
        for i in range(total_requests):
            url = test_urls[i % len(test_urls)]
            task = fetch_url(session, url, semaphore)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
    
    total_time = time.time() - start_time
    
    # Process results
    response_times = [r[0] for r in results]
    status_codes = [r[1] for r in results]
    
    # Calculate statistics
    success_rate = len([s for s in status_codes if s == 200]) / len(status_codes) * 100
    avg_response_time = mean(response_times)
    median_response_time = median(response_times)
    max_response_time = max(response_times)
    rps = total_requests / total_time
    
    # Print results
    print("\nLoad Test Results:")
    print("-" * 50)
    print(f"Total time: {total_time:.2f}s")
    print(f"Requests per second: {rps:.2f}")
    print(f"Success rate: {success_rate:.1f}%")
    print(f"Average response time: {avg_response_time:.3f}s")
    print(f"Median response time: {median_response_time:.3f}s") 
    print(f"Max response time: {max_response_time:.3f}s")
    
    # Performance assessment
    print("\nPerformance Assessment:")
    print("-" * 50)
    
    if avg_response_time < 0.5:
        print("🟢 Excellent response times!")
    elif avg_response_time < 1.0:
        print("🟡 Good response times")
    else:
        print("🔴 Response times may be too slow for HN traffic")
    
    if success_rate > 99:
        print("🟢 Excellent success rate!")
    elif success_rate > 95:
        print("🟡 Good success rate")
    else:
        print("🔴 Success rate too low - check for errors")
    
    if rps > 100:
        print("🟢 Good throughput!")
    elif rps > 50:
        print("🟡 Moderate throughput")
    else:
        print("🔴 Low throughput - may not handle HN traffic")

def main():
    parser = argparse.ArgumentParser(description='Load test your website')
    parser.add_argument('--url', default='http://localhost', help='Base URL to test')
    parser.add_argument('--users', type=int, default=50, help='Concurrent users')
    parser.add_argument('--requests', type=int, default=500, help='Total requests')
    
    args = parser.parse_args()
    
    print("Website Load Tester")
    print("=" * 50)
    
    asyncio.run(load_test(args.url, args.users, args.requests))

if __name__ == "__main__":
    main() 
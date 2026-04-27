# Launch Day Checklist

## 24 Hours Before Launch
- [ ] Run final security audit
- [ ] Test all payment flows
- [ ] Verify email notifications work
- [ ] Check SSL certificate expiry
- [ ] Test on mobile devices
- [ ] Load test with 100 concurrent users

## 1 Hour Before Launch
- [ ] Take final database backup
- [ ] Enable CloudFlare if used
- [ ] Set environment to production
- [ ] Clear caches
- [ ] Restart services

## Launch Time
- [ ] Deploy final code
- [ ] Run database migrations
- [ ] Verify `/health` and `/healthz`
- [ ] Test critical user flows
- [ ] Send launch notification emails

## Post Launch
- [ ] Monitor error logs
- [ ] Check response times
- [ ] Verify order processing
- [ ] Monitor payment gateway
- [ ] Watch customer feedback

## T+24 Hours
- [ ] Review DAU and order volume
- [ ] Review error and payment metrics
- [ ] Fix critical launch bugs
- [ ] Plan next sprint priorities

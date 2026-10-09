"""Audit the current Team7 Perversion receipt; do not mark a floor clear."""
from verify_team_seven_tomorrow import verify

if __name__ == '__main__':
    verify('Perversion', 'team-seven-perversion-real-verification.json')

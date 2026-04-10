'use client';

import { ShoppingBag, Facebook, Twitter, Instagram, Youtube, Mail, Phone, MapPin } from 'lucide-react';
import { Separator } from '@/components/ui/separator';
import { useUIStore } from '@/store';
import type { AppView } from '@/types';

export function SiteFooter() {
  const { navigate } = useUIStore();

  return (
    <footer className="border-t bg-muted/30 mt-auto">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Main footer content */}
        <div className="py-10 md:py-12 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-8 lg:gap-12">
          {/* About */}
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 bg-primary rounded-xl flex items-center justify-center">
                <ShoppingBag className="w-4 h-4 text-primary-foreground" />
              </div>
              <span className="text-lg font-bold text-foreground">
                Smart<span className="text-primary">Dalali</span>
              </span>
            </div>
            <p className="text-sm text-muted-foreground leading-relaxed">
              Tanzania&apos;s premier multi-vendor marketplace. Buy and sell quality products
              from trusted sellers across the country with secure payments and reliable delivery.
            </p>
            {/* Social Links */}
            <div className="flex items-center gap-2">
              <button
                aria-label="Facebook"
                className="w-9 h-9 rounded-full bg-muted hover:bg-primary hover:text-primary-foreground flex items-center justify-center transition-colors"
              >
                <Facebook className="w-4 h-4" />
              </button>
              <button
                aria-label="Twitter"
                className="w-9 h-9 rounded-full bg-muted hover:bg-primary hover:text-primary-foreground flex items-center justify-center transition-colors"
              >
                <Twitter className="w-4 h-4" />
              </button>
              <button
                aria-label="Instagram"
                className="w-9 h-9 rounded-full bg-muted hover:bg-primary hover:text-primary-foreground flex items-center justify-center transition-colors"
              >
                <Instagram className="w-4 h-4" />
              </button>
              <button
                aria-label="YouTube"
                className="w-9 h-9 rounded-full bg-muted hover:bg-primary hover:text-primary-foreground flex items-center justify-center transition-colors"
              >
                <Youtube className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Quick Links */}
          <div className="space-y-4">
            <h4 className="text-sm font-semibold text-foreground uppercase tracking-wider">
              Quick Links
            </h4>
            <ul className="space-y-2.5">
              {([
                { label: 'Home', view: 'home' },
                { label: 'Categories', view: 'home' },
                { label: 'Sell on SmartDalali', view: 'seller-register' },
                { label: 'My Orders', view: 'orders' },
                { label: 'My Profile', view: 'profile' },
              ] as { label: string; view: AppView['view'] }[]).map((link) => (
                <li key={link.label}>
                  <button
                    onClick={() => navigate({ view: link.view } as AppView)}
                    className="text-sm text-muted-foreground hover:text-primary transition-colors"
                  >
                    {link.label}
                  </button>
                </li>
              ))}
            </ul>
          </div>

          {/* Categories */}
          <div className="space-y-4">
            <h4 className="text-sm font-semibold text-foreground uppercase tracking-wider">
              Categories
            </h4>
            <ul className="space-y-2.5">
              {[
                'Electronics',
                'Fashion & Clothing',
                'Home & Garden',
                'Vehicles',
                'Phones & Tablets',
                'Health & Beauty',
              ].map((cat) => (
                <li key={cat}>
                  <button
                    onClick={() => navigate({ view: 'home' })}
                    className="text-sm text-muted-foreground hover:text-primary transition-colors"
                  >
                    {cat}
                  </button>
                </li>
              ))}
            </ul>
          </div>

          {/* Contact */}
          <div className="space-y-4">
            <h4 className="text-sm font-semibold text-foreground uppercase tracking-wider">
              Contact Us
            </h4>
            <ul className="space-y-3">
              <li className="flex items-start gap-2.5 text-sm text-muted-foreground">
                <MapPin className="w-4 h-4 mt-0.5 flex-shrink-0 text-primary" />
                <span>Dar es Salaam, Tanzania, East Africa</span>
              </li>
              <li className="flex items-center gap-2.5 text-sm text-muted-foreground">
                <Phone className="w-4 h-4 flex-shrink-0 text-primary" />
                <span>+255 (0) 800 123 456</span>
              </li>
              <li className="flex items-center gap-2.5 text-sm text-muted-foreground">
                <Mail className="w-4 h-4 flex-shrink-0 text-primary" />
                <span>support@smartdalali.co.tz</span>
              </li>
            </ul>
          </div>
        </div>

        {/* Bottom bar */}
        <Separator />
        <div className="py-5 flex flex-col sm:flex-row items-center justify-between gap-3">
          <p className="text-xs text-muted-foreground text-center sm:text-left">
            © {new Date().getFullYear()} SmartDalali. All rights reserved.
          </p>
          <p className="text-xs text-muted-foreground">
            Powered by{' '}
            <span className="font-semibold text-primary">SmartDalali</span>
          </p>
        </div>
      </div>
    </footer>
  );
}

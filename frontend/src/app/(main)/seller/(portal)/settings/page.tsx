import { SellerSettingsView } from '@/views/seller-settings';
import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Store Settings | Seller Portal | SmartDalali',
  description: 'Manage your store profile, branding, and preferences.',
};

export default function Page() {
  return <SellerSettingsView />;
}

/**
 * i18n.js — Bilingual English / Khmer support for SmartX-Ray.
 *
 * Usage in HTML:
 *   data-i18n="key"              → sets textContent
 *   data-i18n-html="key"         → sets innerHTML (for bold/links inside text)
 *   data-i18n-placeholder="key"  → sets input placeholder
 *   data-i18n-title="key"        → sets title attribute (tooltip)
 *
 * Language is persisted in localStorage("lang").  Default: "en".
 */

const TRANSLATIONS = {

  /* ── Global / Navbar ───────────────────────────────────────────────── */
  nav_dashboard:     { en: "Dashboard",       km: "ផ្ទាំងគ្រប់គ្រង" },
  nav_find_doctor:   { en: "Find a Doctor",   km: "រកវេជ្ជបណ្ឌិត" },
  nav_pricing:       { en: "Pricing",         km: "តម្លៃ" },
  nav_login:         { en: "Login",           km: "ចូល" },
  nav_signup:        { en: "Sign Up Free",    km: "ចុះឈ្មោះឥតគិតថ្លៃ" },
  nav_logout:        { en: "Logout",          km: "ចាកចេញ" },

  /* ── Footer ────────────────────────────────────────────────────────── */
  footer_tagline:    { en: "AI-Powered Pneumonia Detection", km: "ការរកឃើញជំងឺរលាកសួតដោយ AI" },
  footer_disclaimer: { en: "For educational use only. Not a substitute for medical advice.", km: "សម្រាប់តែការប្រើប្រាស់ផ្នែកអប់រំ។ មិនជំនួសការណែនាំពីគ្រូពេទ្យ។" },
  footer_val_acc:    { en: "Val Accuracy:", km: "ភាពត្រឹមត្រូវ:" },

  /* ── Index / Landing ───────────────────────────────────────────────── */
  hero_badge:        { en: "University Research Project",  km: "គម្រោងស្រាវជ្រាវសាកលវិទ្យាល័យ" },
  hero_h1:           { en: "AI-Powered Pneumonia Detection", km: "ការរកឃើញជំងឺរលាកសួតដោយ AI" },
  hero_lead:         { en: "Upload a chest X-ray and get an instant AI diagnosis with Grad-CAM heatmap visualisation — built on a Hybrid CNN+ANN model with <strong>97.03% validation accuracy</strong>.", km: "បញ្ចូលរូបភាព X-ray ទ្រូង ហើយទទួលបានការធ្វើរោគវិនិច្ឆ័យ AI ភ្លាមៗ ជាមួយ Grad-CAM — ផ្អែកលើគំរូ Hybrid CNN+ANN ដែលមាន<strong>ភាពត្រឹមត្រូវ ៩៧.០៣%</strong>។" },
  hero_cta_primary:  { en: "Try Free — No Card Needed",   km: "សាកល្បងឥតគិតថ្លៃ — មិនត្រូវការកាត" },
  hero_cta_plans:    { en: "See Pro Plans",                km: "មើលផែនការ Pro" },
  hero_check1:       { en: "97.03% Val Accuracy",          km: "ភាពត្រឹមត្រូវ ៩៧.០៣%" },
  hero_check2:       { en: "Grad-CAM Heatmaps",            km: "Grad-CAM Heatmaps" },
  hero_check3:       { en: "Free tier: 3 scans/day",       km: "ឥតគិតថ្លៃ: ៣ ដង/ថ្ងៃ" },

  stat_val_acc:      { en: "Validation Accuracy",   km: "ភាពត្រឹមត្រូវវ៉ាលីដេស្យុង" },
  stat_test_acc:     { en: "Test Accuracy",          km: "ភាពត្រឹមត្រូវសាកល្បង" },
  stat_architecture: { en: "Hybrid Architecture",   km: "រចនាសម្ព័ន្ធចម្រុះ" },
  stat_xai:          { en: "Explainable AI",         km: "AI ដែលអាចពន្យល់បាន" },

  features_title:    { en: "Everything You Need",         km: "អ្វីៗដែលអ្នកត្រូវការ" },
  feat1_title:       { en: "Instant Results",             km: "លទ្ធផលភ្លាមៗ" },
  feat1_body:        { en: "Upload an X-ray and receive a PNEUMONIA / NORMAL prediction in seconds.", km: "បញ្ចូល X-ray ហើយទទួលការព្យាករ PNEUMONIA / NORMAL ក្នុងរយៈពេលប៉ុន្មានវិនាទី។" },
  feat2_title:       { en: "Grad-CAM Heatmaps",           km: "Grad-CAM Heatmaps" },
  feat2_body:        { en: "Visualise exactly which regions of the X-ray drove the AI's decision.", km: "មើលឃើញពិតប្រាកដថាតំបន់ណាខ្លះនៃ X-ray ដែលបណ្តាលឱ្យ AI សម្រេចចិត្ត។" },
  feat3_title:       { en: "PDF Reports",                 km: "របាយការណ៍ PDF" },
  feat3_body:        { en: "Download a branded diagnostic PDF with images, heatmaps, and clinical notes.", km: "ទាញយករបាយការណ៍ PDF ដែលមានរូបភាព, heatmaps, និងចំណាំគ្លីនិក។" },
  feat4_title:       { en: "Find a Doctor",               km: "រកវេជ្ជបណ្ឌិត" },
  feat4_body:        { en: "Connect with verified pulmonologists and radiologists near you.", km: "ភ្ជាប់ជាមួយអ្នកឯកទេសសួត និងគ្រូពេទ្យ X-ray ដែលត្រូវបានផ្ទៀងផ្ទាត់ជិតអ្នក។" },

  how_title:         { en: "How It Works",      km: "របៀបដំណើរការ" },
  how1_title:        { en: "Upload X-Ray",      km: "បញ្ចូល X-Ray" },
  how1_body:         { en: "Drag and drop a chest X-ray PNG or JPEG file (up to 16 MB).", km: "ទាញ និងទម្លាក់ឯកសារ PNG ឬ JPEG X-ray ទ្រូង (រហូតដល់ ១៦ MB)។" },
  how2_title:        { en: "AI Analysis",       km: "ការវិភាគ AI" },
  how2_body:         { en: "Our Hybrid CNN+ANN model analyses the image and produces a prediction with Grad-CAM.", km: "គំរូ Hybrid CNN+ANN របស់យើងវិភាគរូបភាព ហើយផ្តល់ការព្យាករជាមួយ Grad-CAM។" },
  how3_title:        { en: "Review Results",    km: "ពិនិត្យលទ្ធផល" },
  how3_body:         { en: "See the result, confidence score, heatmap, and (Pro) download a full PDF report.", km: "មើលលទ្ធផល, ពិន្ទុទំនុកចិត្ត, heatmap, និង (Pro) ទាញយករបាយការណ៍ PDFពេញ។" },

  pricing_preview_title: { en: "Simple, Transparent Pricing", km: "តម្លៃ សាមញ្ញ ច្បាស់លាស់" },
  pricing_preview_sub:   { en: "Start free. Upgrade anytime.", km: "ចាប់ផ្តើមឥតគិតថ្លៃ។ ធ្វើឱ្យប្រសើរគ្រប់ពេល។" },
  plan_free:             { en: "Free",            km: "ឥតគិតថ្លៃ" },
  plan_forever:          { en: "forever",         km: "សម្រាប់អស់មួយជីវិត" },
  plan_3scans:           { en: "3 scans per day", km: "៣ ដងក្នុងមួយថ្ងៃ" },
  plan_heatmaps:         { en: "Grad-CAM heatmaps", km: "Grad-CAM heatmaps" },
  plan_history:          { en: "Scan history",    km: "ប្រវត្តិស្កែន" },
  plan_no_pdf:           { en: "PDF reports",     km: "របាយការណ៍ PDF" },
  plan_no_adfree:        { en: "Ad-free experience", km: "គ្មានការផ្សាយពាណិជ្ជកម្ម" },
  plan_get_free:         { en: "Get Started Free", km: "ចាប់ផ្តើមឥតគិតថ្លៃ" },
  plan_pro:              { en: "Pro",              km: "Pro" },
  plan_most_popular:     { en: "MOST POPULAR",    km: "ពេញនិយមបំផុត" },
  plan_unlimited:        { en: "Unlimited scans", km: "ស្កែនគ្មានដែនកំណត់" },
  plan_pdf:              { en: "PDF diagnostic reports", km: "របាយការណ៍ PDF" },
  plan_adfree:           { en: "Ad-free experience", km: "គ្មានការផ្សាយពាណិជ្ជកម្ម" },
  plan_priority:         { en: "Priority support",    km: "ការគាំទ្រអាទិភាព" },
  plan_upgrade:          { en: "Upgrade to Pro",      km: "ធ្វើឱ្យប្រសើរទៅ Pro" },
  plan_subscribe:        { en: "Subscribe Now",       km: "ចុះឈ្មោះឥឡូវ" },

  cta_title:   { en: "Ready to analyse your first X-ray?", km: "រួចរាល់ក្នុងការវិភាគ X-ray ដំបូងរបស់អ្នក?" },
  cta_sub:     { en: "No credit card required. Start free in 30 seconds.", km: "មិនត្រូវការប័ណ្ណឥណទាន។ ចាប់ផ្តើមឥតគិតថ្លៃក្នុង ៣០ វិនាទី។" },
  cta_btn:     { en: "Upload X-Ray Now", km: "បញ្ចូល X-Ray ឥឡូវ" },

  /* ── Dashboard ─────────────────────────────────────────────────────── */
  dash_title:          { en: "My Dashboard",          km: "ផ្ទាំងគ្រប់គ្រងរបស់ខ្ញុំ" },
  dash_upgrade:        { en: "Upgrade to Pro",        km: "ធ្វើឱ្យប្រសើរទៅ Pro" },
  dash_daily_scans:    { en: "Daily Scans",           km: "ស្កែនប្រចាំថ្ងៃ" },
  dash_resets:         { en: "Resets at midnight UTC.", km: "កំណត់ឡើងវិញពេលធ្ងន់ UTC។" },
  dash_unlimited_link: { en: "Upgrade for unlimited scans →", km: "ធ្វើឱ្យប្រសើរដើម្បីស្កែនគ្មានដែនកំណត់ →" },
  dash_upload_title:   { en: "Upload X-Ray",          km: "បញ្ចូល X-Ray" },
  dash_drop:           { en: "Drag & drop your X-ray here", km: "ទាញ និងទម្លាក់ X-ray របស់អ្នកទីនេះ" },
  dash_drop_sub:       { en: "PNG, JPG, JPEG · Max 16 MB", km: "PNG, JPG, JPEG · អតិបរមា ១៦ MB" },
  dash_browse:         { en: "Browse File",            km: "រកឯកសារ" },
  dash_analyse:        { en: "Analyse Now",            km: "វិភាគឥឡូវ" },
  dash_clear:          { en: "Clear",                  km: "លុប" },
  dash_history:        { en: "Scan History",           km: "ប្រវត្តិស្កែន" },
  dash_loading_scans:  { en: "Loading scans…",         km: "កំពុងផ្ទុក…" },
  dash_load_more:      { en: "Load More",              km: "ផ្ទុកបន្ថែម" },
  dash_no_scans:       { en: "No scans yet. Upload your first X-ray above!", km: "មិនទាន់មានស្កែន។ បញ្ចូល X-ray ដំបូងរបស់អ្នកខាងលើ!" },
  dash_account:        { en: "Account",                km: "គណនី" },
  dash_logged_as:      { en: "Logged in as",           km: "ចូលជា" },
  dash_manage_sub:     { en: "Manage Subscription",   km: "គ្រប់គ្រងការជាវ" },
  dash_find_doctor:    { en: "Find a Doctor",          km: "រកវេជ្ជបណ្ឌិត" },
  dash_pro_features:   { en: "Pro Features",           km: "មុខងារ Pro" },
  dash_pro_unlimited:  { en: "Unlimited scans",        km: "ស្កែនគ្មានដែនកំណត់" },
  dash_pro_pdf:        { en: "PDF diagnostic reports", km: "របាយការណ៍ PDF" },
  dash_pro_no_ads:     { en: "No advertisements",      km: "គ្មានការផ្សាយពាណិជ្ជកម្ម" },
  dash_pro_upgrade:    { en: "Upgrade — from $9.99/mo", km: "ធ្វើឱ្យប្រសើរ — ពី $9.99/ខែ" },
  dash_quick_stats:    { en: "Quick Stats",            km: "ស្ថិតិរហ័ស" },
  dash_total_scans:    { en: "Total Scans",            km: "ស្កែនសរុប" },
  dash_pneumonia:      { en: "Pneumonia",              km: "ជំងឺរលាកសួត" },
  dash_advertisement:  { en: "Advertisement",          km: "ការផ្សាយពាណិជ្ជកម្ម" },
  dash_learn_more:     { en: "Learn More",             km: "ស្វែងយល់បន្ថែម" },
  dash_confidence:     { en: "confidence",             km: "ទំនុកចិត្ត" },
  dash_analysing:      { en: "Analysing X-ray… This may take a few seconds.", km: "កំពុងវិភាគ X-ray… អាចចំណាយពេលប៉ុន្មានវិនាទី។" },
  dash_analysis_done:  { en: "Analysis complete!",     km: "ការវិភាគបានបញ្ចប់!" },
  dash_upload_failed:  { en: "Upload failed.",         km: "បញ្ចូលបានបរាជ័យ។" },
  dash_error:          { en: "An error occurred. Please try again.", km: "មានកំហុសកើតឡើង។ សូមព្យាយាមម្តងទៀត។" },
  dash_view:           { en: "View",                   km: "មើល" },

  /* ── Result page ───────────────────────────────────────────────────── */
  result_breadcrumb:   { en: "Dashboard",               km: "ផ្ទាំងគ្រប់គ្រង" },
  result_confidence:   { en: "Confidence",              km: "ទំនុកចិត្ត" },
  result_pneumonia_msg:{ en: "The AI detected patterns consistent with <strong>pneumonia</strong>. Please consult a physician.", km: "AI បានរកឃើញទំរង់ដែលស្របនឹង<strong>ជំងឺរលាកសួត</strong>។ សូមពិគ្រោះជាមួយគ្រូពេទ្យ។" },
  result_normal_msg:   { en: "The AI found <strong>no significant pneumonia patterns</strong>. Always verify with a doctor.", km: "AI រកឃើញ<strong>គ្មានទំរង់ជំងឺរលាកសួតសំខាន់</strong>។ សូមផ្ទៀងផ្ទាត់ជានិច្ចជាមួយគ្រូពេទ្យ។" },
  result_pdf_btn:      { en: "Download PDF Report",     km: "ទាញយករបាយការណ៍ PDF" },
  result_pdf_locked:   { en: "PDF reports are a <strong>Pro</strong> feature. <a href=\"/pricing\" class=\"alert-link\">Upgrade for $9.99/month →</a>", km: "របាយការណ៍ PDF គឺជាមុខងារ <strong>Pro</strong>។ <a href=\"/pricing\" class=\"alert-link\">ធ្វើឱ្យប្រសើរ $9.99/ខែ →</a>" },
  result_generating:   { en: "Report is being generated…", km: "កំពុងបង្កើតរបាយការណ៍…" },
  result_back:         { en: "Dashboard",               km: "ផ្ទាំងគ្រប់គ្រង" },
  result_find_doctor:  { en: "Find a Doctor",           km: "រកវេជ្ជបណ្ឌិត" },
  result_original:     { en: "Original X-Ray",          km: "X-Ray ដើម" },
  result_heatmap:      { en: "Grad-CAM Heatmap",        km: "Grad-CAM Heatmap" },
  result_xai_badge:    { en: "Explainable AI",          km: "AI ដែលអាចពន្យល់" },
  result_legend_title: { en: "Reading the Heatmap",     km: "ការអានតម្លៃ Heatmap" },
  result_legend_desc:  { en: "Cool → Warm: low → high AI attention", km: "ត្រជាក់ → ក្តៅ: ការយកចិត្ត AI ទាប → ខ្ពស់" },
  result_legend_body:  { en: "Red/yellow regions indicate areas the model weighted most heavily when making its prediction.", km: "តំបន់ពណ៌ក្រហម/លឿងបង្ហាញតំបន់ដែលគំរូបានផ្តល់ទម្ងន់ច្រើនបំផុតក្នុងការព្យាករ។" },
  result_disclaimer:   { en: "<strong>Disclaimer:</strong> This is an AI-assisted analysis tool for educational purposes only. It is <strong>not</strong> a substitute for professional medical diagnosis. Always consult a qualified physician.", km: "<strong>ការបដិសេធ:</strong> នេះជាឧបករណ៍វិភាគដោយ AI សម្រាប់តែការអប់រំ។ វា<strong>មិន</strong>ជំនួសសម្រាប់ការធ្វើរោគវិនិច្ឆ័យពីគ្រូពេទ្យ។ សូមពិគ្រោះជាមួយគ្រូពេទ្យដែលមានសមត្ថភាព។" },
  result_no_image:     { en: "Image not available",     km: "រូបភាពមិនអាចប្រើ" },
  result_heatmap_unavail: { en: "Heatmap unavailable",  km: "Heatmap មិនអាចប្រើ" },
  result_generating_hm:   { en: "Generating…",          km: "កំពុងបង្កើត…" },
  result_not_found:    { en: "Scan not found.",         km: "រកស្កែនមិនឃើញ។" },

  /* ── Pricing page ──────────────────────────────────────────────────── */
  pricing_title:       { en: "Simple, Transparent Pricing",    km: "តម្លៃ សាមញ្ញ ច្បាស់លាស់" },
  pricing_sub:         { en: "Upgrade anytime. Cancel anytime. No hidden fees.", km: "ធ្វើឱ្យប្រសើរគ្រប់ពេល។ បោះបង់គ្រប់ពេល។ គ្មានថ្លៃលាក់ស្ងាត់។" },
  pricing_monthly:     { en: "Monthly",                        km: "ប្រចាំខែ" },
  pricing_yearly:      { en: "Yearly",                         km: "ប្រចាំឆ្នាំ" },
  pricing_save:        { en: "Save 33%",                       km: "សន្សំ ៣៣%" },
  pricing_marketplace: { en: "Marketplace access",            km: "ចូលប្រើទីផ្សារ" },
  pricing_secure:      { en: "Secure payment via Stripe",     km: "ការទូទាត់ដោយសុវត្ថិភាពតាម Stripe" },

  faq_title:     { en: "Frequently Asked Questions", km: "សំណួរដែលសួរញឹកញាប់" },
  faq1_q:        { en: "Can I cancel at any time?", km: "តើខ្ញុំអាចបោះបង់គ្រប់ពេលបានទេ?" },
  faq1_a:        { en: "Yes. You can cancel your subscription from your dashboard at any time. You retain Pro access until the end of the current billing period.", km: "បាទ/ចាស។ អ្នកអាចបោះបង់ការជាវពីផ្ទាំងគ្រប់គ្រងរបស់អ្នកគ្រប់ពេល។ អ្នកនៅតែមានការចូលប្រើ Pro រហូតដល់ចុងនៃរយៈពេលចេញវិក្កយបត្របច្ចុប្បន្ន។" },
  faq2_q:        { en: "Is this a real medical diagnostic tool?", km: "តើនេះជាឧបករណ៍វិភាគវេជ្ជសាស្ត្រពិតប្រាកដទេ?" },
  faq2_a:        { en: "No. SmartX-Ray is a university research project for educational purposes only. It is <strong>not</strong> a certified medical device and must not be used as a substitute for professional medical advice or diagnosis.", km: "ទេ។ SmartX-Ray គឺជាគម្រោងស្រាវជ្រាវសាកលវិទ្យាល័យសម្រាប់តែការអប់រំ។ វា<strong>មិន</strong>ជាឧបករណ៍វេជ្ជសាស្ត្រដែលបានទទួលស្គាល់ ហើយមិនត្រូវប្រើជំនួសការណែនាំ ឬការធ្វើរោគវិនិច្ឆ័យពីគ្រូពេទ្យ។" },
  faq3_q:        { en: "What payment methods are accepted?", km: "តើទទួលទូទាត់ដោយរបៀបណាខ្លះ?" },
  faq3_a:        { en: "All major credit and debit cards via Stripe (Visa, Mastercard, Amex). Payments are processed securely — SmartX-Ray never stores your card details.", km: "ប័ណ្ណឥណទាន និងប័ណ្ណឥណពន្ធធំៗទាំងអស់តាម Stripe (Visa, Mastercard, Amex)។ ការទូទាត់ត្រូវបានដំណើរការដោយសុវត្ថិភាព — SmartX-Ray មិនដែលរក្សាទុកព័ត៌មានកាតរបស់អ្នក។" },
  faq4_q:        { en: "What happens to my scans if I downgrade?", km: "តើអ្វីកើតឡើងចំពោះស្កែនរបស់ខ្ញុំប្រសិនបើខ្ញុំបន្ថយថ្នាក់?" },
  faq4_a:        { en: "Your scan history and all previously generated PDF reports remain accessible. New scans revert to the 3/day limit and PDF generation stops.", km: "ប្រវត្តិស្កែន និងរបាយការណ៍ PDF ដែលបានបង្កើតពីមុននៅអាចចូលប្រើបាន។ ការស្កែនថ្មីត្រឡប់ទៅដែនកំណត់ ៣/ថ្ងៃ ហើយការបង្កើត PDF ឈប់ដំណើរការ។" },

  /* ── Auth page ─────────────────────────────────────────────────────── */
  auth_tagline:    { en: "AI-Powered Pneumonia Detection", km: "ការរកឃើញជំងឺរលាកសួតដោយ AI" },
  auth_login_tab:  { en: "Login",                km: "ចូល" },
  auth_signup_tab: { en: "Sign Up Free",         km: "ចុះឈ្មោះឥតគិតថ្លៃ" },
  auth_email:      { en: "Email",                km: "អ៊ីមែល" },
  auth_password:   { en: "Password",             km: "ពាក្យសម្ងាត់" },
  auth_forgot:     { en: "Forgot your password?", km: "ភ្លេចពាក្យសម្ងាត់?" },
  auth_login_btn:  { en: "Login",                km: "ចូល" },
  auth_fullname:   { en: "Full Name",            km: "ឈ្មោះពេញ" },
  auth_min8:       { en: "Min 8 characters",     km: "យ៉ាងហោចណាស់ ៨ តួ" },
  auth_create_btn: { en: "Create Free Account",  km: "បង្កើតគណនីឥតគិតថ្លៃ" },
  auth_disclaimer: { en: "By signing up you agree to use this app for educational purposes only.<br>Not a substitute for professional medical advice.", km: "ដោយចុះឈ្មោះ អ្នកយល់ព្រមប្រើកម្មវិធីនេះសម្រាប់តែការអប់រំ។<br>មិនជំនួសសម្រាប់ការណែនាំពីគ្រូពេទ្យ។" },

  /* ── Forgot / Reset password ───────────────────────────────────────── */
  forgot_title:    { en: "Forgot your password?",    km: "ភ្លេចពាក្យសម្ងាត់?" },
  forgot_sub:      { en: "Enter your email and we'll send a reset link.", km: "បញ្ចូលអ៊ីមែលរបស់អ្នក ហើយយើងនឹងផ្ញើតំណផ្ទៀងផ្ទាត់។" },
  forgot_email_label: { en: "Email Address",         km: "អាសយដ្ឋានអ៊ីមែល" },
  forgot_send_btn: { en: "Send Reset Link",          km: "ផ្ញើតំណកំណត់ម្ដងទៀត" },
  forgot_success_h:{ en: "Check your inbox",         km: "ពិនិត្យប្រអប់ទទួលរបស់អ្នក" },
  forgot_success_p:{ en: "If that email is registered you'll receive a reset link shortly. The link expires in 30 minutes.", km: "ប្រសិនបើអ៊ីមែលនោះត្រូវបានចុះឈ្មោះ អ្នកនឹងទទួលបានតំណក្នុងពេលឆាប់ៗ។ តំណនេះផុតកំណត់ក្នុង ៣០ នាទី។" },
  forgot_remembered:{ en: "Remembered it?",          km: "ចាំហើយ?" },
  forgot_login:    { en: "Log in →",                km: "ចូល →" },

  /* ── Marketplace page ──────────────────────────────────────────────── */
  market_title:    { en: "Find a Doctor",        km: "រកវេជ្ជបណ្ឌិត" },
  market_sub:      { en: "Connect with verified pulmonologists and radiologists near you.", km: "ភ្ជាប់ជាមួយអ្នកឯកទេសសួត និងគ្រូពេទ្យ X-ray ដែលត្រូវបានផ្ទៀងផ្ទាត់ជិតអ្នក។" },
  market_search_label: { en: "Search",           km: "ស្វែងរក" },
  market_specialty:{ en: "Specialty",            km: "ជំនាញ" },
  market_city:     { en: "City",                 km: "ក្រុង" },
  market_reset:    { en: "Reset",                km: "កំណត់ម្ដងទៀត" },
  market_featured: { en: "Featured doctors only", km: "តែវេជ្ជបណ្ឌិតដែលលេចធ្លោ" },
  market_all_spec: { en: "All Specialties",      km: "ជំនាញទាំងអស់" },
  market_all_cities: { en: "All Cities",         km: "ក្រុងទាំងអស់" },
  market_loading:  { en: "Loading…",             km: "កំពុងផ្ទុក…" },
  market_load_more:{ en: "Load More",            km: "ផ្ទុកបន្ថែម" },
  market_no_results: { en: "No doctors found matching your criteria.", km: "រកមិនឃើញវេជ្ជបណ្ឌិតដែលត្រូវនឹងលក្ខណៈរបស់អ្នក។" },
  market_clear_filters: { en: "Clear Filters",  km: "លប់តម្រង" },
  market_verified: { en: "Verified",             km: "បានផ្ទៀងផ្ទាត់" },
  market_featured_badge: { en: "Featured",       km: "លេចធ្លោ" },
  market_reviews:  { en: "reviews",              km: "មតិ" },
  market_call:     { en: "Call",                 km: "ហៅ" },
  market_email:    { en: "Email",                km: "អ៊ីមែល" },
  market_map:      { en: "Map",                  km: "ផែនទី" },
  market_placeholder_search: { en: "Name, hospital…", km: "ឈ្មោះ, មន្ទីរពេទ្យ…" },

  /* ── Admin Panel ───────────────────────────────────────────────────── */
  // Sidebar
  adm_brand_sub:      { en: "Admin Panel",              km: "បន្ទប់គ្រប់គ្រង" },
  adm_nav_overview:   { en: "Overview",                 km: "ទិដ្ឋភាពទូទៅ" },
  adm_nav_dashboard:  { en: "Dashboard",                km: "ផ្ទាំងគ្រប់គ្រង" },
  adm_nav_management: { en: "Management",               km: "ការគ្រប់គ្រង" },
  adm_nav_users:      { en: "Users",                    km: "អ្នកប្រើប្រាស់" },
  adm_nav_ads:        { en: "Ad Manager",               km: "គ្រប់គ្រងការផ្សាយ" },
  adm_nav_subs:       { en: "Subscriptions",            km: "ការជាវ" },
  adm_nav_marketplace:{ en: "Marketplace",              km: "ផ្សារ" },
  adm_nav_system:     { en: "System",                   km: "ប្រព័ន្ធ" },
  adm_nav_logs:       { en: "System Logs",              km: "កំណត់ហេតុប្រព័ន្ធ" },
  adm_nav_health:     { en: "Health Check",             km: "ពិនិត្យសុខភាព" },
  adm_back_app:       { en: "Back to App",              km: "ត្រឡប់ទៅកម្មវិធី" },
  adm_logout:         { en: "Logout",                   km: "ចាកចេញ" },
  adm_refresh:        { en: "Refresh",                  km: "ធ្វើឱ្យស្រស់" },

  // Dashboard page
  adm_dash_title:     { en: "Dashboard Overview",       km: "ទិដ្ឋភាពទូទៅ" },
  adm_dash_sub:       { en: "SmartX-Ray — Cambodia Medical AI Platform", km: "SmartX-Ray — វេទិកា AI វេជ្ជសាស្ត្រកម្ពុជា" },
  adm_total_users:    { en: "Total Users",              km: "អ្នកប្រើប្រាស់សរុប" },
  adm_total_scans:    { en: "Total Scans",              km: "ស្កែនសរុប" },
  adm_today:          { en: "Today:",                   km: "ថ្ងៃនេះ:" },
  adm_active_subs:    { en: "Active Subscriptions",     km: "ការជាវសកម្ម" },
  adm_est:            { en: "est.",                     km: "ប៉ាន់ស្មាន" },
  adm_pending_docs:   { en: "Pending Doctors",          km: "វេជ្ជបណ្ឌិតរង់ចាំ" },
  adm_awaiting:       { en: "Awaiting approval",        km: "រង់ចាំការអនុម័ត" },
  adm_scan_results:   { en: "Scan Results",             km: "លទ្ធផលស្កែន" },
  adm_pneumonia:      { en: "Pneumonia",                km: "ជំងឺរលាកសួត" },
  adm_normal:         { en: "Normal",                   km: "ធម្មតា" },
  adm_pneu_rate:      { en: "Pneumonia rate",           km: "អត្រាជំងឺរលាកសួត" },
  adm_ad_perf:        { en: "Ad Performance",           km: "ការអនុវត្តការផ្សាយ" },
  adm_active_ads:     { en: "Active Ads",               km: "ការផ្សាយសកម្ម" },
  adm_impressions:    { en: "Impressions",              km: "ការបង្ហាញ" },
  adm_clicks:         { en: "Clicks",                   km: "ចុច" },
  adm_manage_ads:     { en: "Manage Ads",               km: "គ្រប់គ្រងការផ្សាយ" },
  adm_quick_actions:  { en: "Quick Actions",            km: "សកម្មភាពរហ័ស" },
  adm_manage_users:   { en: "Manage Users",             km: "គ្រប់គ្រងអ្នកប្រើ" },
  adm_doc_approvals:  { en: "Doctor Approvals",         km: "ការអនុម័តវេជ្ជបណ្ឌិត" },

  // Users page
  adm_user_title:     { en: "User Management",          km: "ការគ្រប់គ្រងអ្នកប្រើ" },
  adm_user_sub:       { en: "Filter, promote, and suspend user accounts", km: "តម្រង លើកកម្ពស់ និងព្យួរគណនី" },
  adm_all_tiers:      { en: "All Tiers",                km: "ស្រទាប់ទាំងអស់" },
  adm_all_uni:        { en: "All Universities",         km: "សាកលវិទ្យាល័យទាំងអស់" },
  adm_all_status:     { en: "All Status",               km: "ស្ថានភាពទាំងអស់" },
  adm_active:         { en: "Active",                   km: "សកម្ម" },
  adm_suspended:      { en: "Suspended",                km: "ព្យួរ" },
  adm_search:         { en: "Search",                   km: "ស្វែងរក" },
  adm_col_user:       { en: "User",                     km: "អ្នកប្រើ" },
  adm_col_university: { en: "University",               km: "សាកលវិទ្យាល័យ" },
  adm_col_tier:       { en: "Tier",                     km: "ស្រទាប់" },
  adm_col_status:     { en: "Status",                   km: "ស្ថានភាព" },
  adm_col_scans:      { en: "Scans Today",              km: "ស្កែនថ្ងៃនេះ" },
  adm_col_joined:     { en: "Joined",                   km: "ចូលរួម" },
  adm_col_actions:    { en: "Actions",                  km: "សកម្មភាព" },
  adm_change_tier:    { en: "Change Tier",              km: "ផ្លាស់ប្ដូរស្រទាប់" },

  // Ads page
  adm_ad_title:       { en: "Ad Manager",               km: "គ្រប់គ្រងការផ្សាយ" },
  adm_ad_sub:         { en: "Upload banners, track CTR, toggle active/inactive", km: "បញ្ចូលបដា តាមដាន CTR ប្ដូរ active/inactive" },
  adm_new_ad:         { en: "New Ad",                   km: "ការផ្សាយថ្មី" },
  adm_col_ad:         { en: "Ad",                       km: "ការផ្សាយ" },
  adm_col_placement:  { en: "Placement",                km: "ទីតាំង" },
  adm_col_priority:   { en: "Priority",                 km: "អាទិភាព" },
  adm_create_ad:      { en: "Create New Ad",            km: "បង្កើតការផ្សាយថ្មី" },
  adm_ad_title_lbl:   { en: "Title",                    km: "ចំណងជើង" },
  adm_ad_advertiser:  { en: "Advertiser",               km: "អ្នកផ្សាយ" },
  adm_ad_body:        { en: "Body Text",                km: "អត្ថបទ" },
  adm_ad_image_url:   { en: "Image URL",                km: "URL រូបភាព" },
  adm_ad_target_url:  { en: "Target URL",               km: "URL គោលដៅ" },
  adm_ad_status:      { en: "Status",                   km: "ស្ថានភាព" },

  // Subscriptions page
  adm_sub_title:      { en: "Subscriptions",            km: "ការជាវ" },
  adm_sub_sub:        { en: "Free vs Pro counts, revenue, and expiry dates", km: "ចំនួន Free ទល់ Pro ចំណូល និងថ្ងៃផុតកំណត់" },
  adm_monthly_subs:   { en: "Monthly Subscribers",      km: "អ្នកជាវប្រចាំខែ" },
  adm_yearly_subs:    { en: "Yearly Subscribers",       km: "អ្នកជាវប្រចាំឆ្នាំ" },
  adm_total_rev:      { en: "Total Revenue (est.)",     km: "ចំណូលសរុប (ប៉ាន់ស្មាន)" },
  adm_active_count:   { en: "Active Subscriptions",     km: "ការជាវសកម្ម" },
  adm_aba_plans:      { en: "ABA KHQR Pricing Plans",   km: "ផែនការតម្លៃ ABA KHQR" },
  adm_monthly_plan:   { en: "Monthly Plan",             km: "ផែនការប្រចាំខែ" },
  adm_yearly_plan:    { en: "Yearly Plan",              km: "ផែនការប្រចាំឆ្នាំ" },
  adm_col_plan:       { en: "Plan",                     km: "ផែនការ" },
  adm_col_renewal:    { en: "Renewal Date",             km: "ថ្ងៃបន្ត" },
  adm_col_autorenew:  { en: "Auto-Renew",               km: "បន្តស្វ័យប្រវត្តិ" },
  adm_col_since:      { en: "Since",                    km: "តាំងពី" },
  adm_save_pct:       { en: "33% off",                  km: "បញ្ចុះ ៣៣%" },

  // Marketplace page
  adm_mkt_title:      { en: "Doctor Marketplace",       km: "ផ្សារវេជ្ជបណ្ឌិត" },
  adm_mkt_sub:        { en: "Review Cambodian doctor license submissions — approve or reject", km: "ពិនិត្យការដាក់ស្នើអាជ្ញាបណ្ណ — អនុម័ត ឬបដិសេធ" },
  adm_pending:        { en: "Pending",                  km: "រង់ចាំ" },
  adm_approved:       { en: "Approved",                 km: "បានអនុម័ត" },
  adm_rejected:       { en: "Rejected",                 km: "បានបដិសេធ" },
  adm_approve:        { en: "Approve",                  km: "អនុម័ត" },
  adm_reject:         { en: "Reject",                   km: "បដិសេធ" },

  // Logs page
  adm_log_title:      { en: "System Logs",              km: "កំណត់ហេតុប្រព័ន្ធ" },
  adm_log_sub:        { en: "Every scan, AI processing time, auth events, and DB health checks", km: "ស្កែនទាំងអស់ ពេលដំណើរការ AI ព្រឹត្តិការ auth និងការពិនិត្យ DB" },
  adm_all_severity:   { en: "All Severity",             km: "ភាពធ្ងន់ទាំងអស់" },
  adm_all_events:     { en: "All Events",               km: "ព្រឹត្តិការណ៍ទាំងអស់" },
  adm_filter:         { en: "Filter",                   km: "តម្រង" },
  adm_col_time:       { en: "Time",                     km: "ពេលវេលា" },
  adm_col_event:      { en: "Event",                    km: "ព្រឹត្តិការណ៍" },
  adm_col_severity:   { en: "Severity",                 km: "ភាពធ្ងន់ធ្ងរ" },
  adm_col_message:    { en: "Message",                  km: "សារ" },
  adm_col_ai_ms:      { en: "AI (ms)",                  km: "AI (ms)" },
  adm_col_ip:         { en: "IP",                       km: "IP" },

  // Login page
  adm_login_sub:      { en: "Admin Panel — Authorized Access Only", km: "បន្ទប់គ្រប់គ្រង — ចូលតែម្ចាស់អំណាច" },
  adm_email_lbl:      { en: "Email",                    km: "អ៊ីមែល" },
  adm_pwd_lbl:        { en: "Password",                 km: "ពាក្យសម្ងាត់" },
  adm_sign_in:        { en: "Sign In",                  km: "ចូល" },
  adm_return_app:     { en: "Return to App",            km: "ត្រឡប់ទៅកម្មវិធី" },
};

/* ── Core engine ──────────────────────────────────────────────────────── */

const I18n = (() => {
  const STORAGE_KEY = "smartxray_lang";
  let current = localStorage.getItem(STORAGE_KEY) || "en";

  function t(key) {
    const entry = TRANSLATIONS[key];
    if (!entry) return key;
    return entry[current] || entry.en || key;
  }

  function applyAll() {
    // text content
    document.querySelectorAll("[data-i18n]").forEach(el => {
      el.textContent = t(el.dataset.i18n);
    });
    // innerHTML (for bold / links inside translated string)
    document.querySelectorAll("[data-i18n-html]").forEach(el => {
      el.innerHTML = t(el.dataset.i18nHtml);
    });
    // placeholder
    document.querySelectorAll("[data-i18n-placeholder]").forEach(el => {
      el.placeholder = t(el.dataset.i18nPlaceholder);
    });
    // title attribute
    document.querySelectorAll("[data-i18n-title]").forEach(el => {
      el.title = t(el.dataset.i18nTitle);
    });
    // Update html lang attribute
    document.documentElement.lang = current === "km" ? "km" : "en";
    // Update toggle button label
    const btn = document.getElementById("langToggleBtn");
    if (btn) btn.textContent = current === "km" ? "EN" : "ខ្មែរ";
  }

  function setLang(lang) {
    current = lang;
    localStorage.setItem(STORAGE_KEY, lang);
    applyAll();
  }

  function toggle() {
    setLang(current === "en" ? "km" : "en");
  }

  function getLang() { return current; }

  // Auto-apply once DOM is ready
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", applyAll);
  } else {
    applyAll();
  }

  return { t, toggle, setLang, getLang, applyAll };
})();

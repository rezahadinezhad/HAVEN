export type Language = "en" | "fa";
const fa: Record<string, string> = {
  "Your sign-in expired or was revoked. Your vault is locked. Sign in again to continue.":
    "ورود شما منقضی یا لغو شده است. مخزن قفل شد. برای ادامه دوباره وارد حساب شوید.",
  "Unlock with this device": "باز کردن با این دستگاه",
  "Your device will require verification, which may use fingerprint, face, or device PIN. Your vault passphrase remains the fallback.":
    "دستگاه برای اثر انگشت، چهره یا پین خود تأیید می‌خواهد. عبارت ورود مخزن همچنان راه جایگزین است.",
  "You can save this separate vault passphrase in your password manager and use its device verification to fill it.":
    "می‌توانید عبارت جداگانهٔ مخزن را در مدیر رمز عبور ذخیره کنید و با تأیید دستگاه آن را وارد کنید.",
  "Built-in device unlock needs a trusted hostname. Direct IP addresses cannot use browser passkeys; your vault remains protected by its passphrase.":
    "باز کردن با دستگاه به نام میزبان مورد اعتماد نیاز دارد. نشانی آی‌پی مستقیم از کلید عبور مرورگر پشتیبانی نمی‌کند؛ مخزن با عبارت ورود محافظت می‌شود.",
  "After you unlock with your vault passphrase, you can set up a device prompt for future visits. HAVEN encrypts a local copy of the passphrase with a passkey PRF; it never sends it to the server.":
    "پس از باز کردن مخزن با عبارت ورود، می‌توانید برای دفعات بعد تأیید دستگاه را تنظیم کنید. هیون نسخه‌ای محلی و رمزگذاری‌شده از عبارت را با PRF کلید عبور نگه می‌دارد و آن را به سرور نمی‌فرستد.",
  "Device unlock is set up on this browser.":
    "باز کردن با دستگاه در این مرورگر تنظیم شده است.",
  "Set up device unlock to use fingerprint, face, or device PIN verification where your device supports it.":
    "اگر دستگاه پشتیبانی کند، باز کردن با اثر انگشت، چهره یا پین دستگاه را تنظیم کنید.",
  "Remove device unlock": "حذف باز کردن با دستگاه",
  "Set up device unlock": "تنظیم باز کردن با دستگاه",
  "This IP-only address cannot use browser passkeys. Use your password manager to fill the vault passphrase; a trusted hostname is required for built-in device unlock.":
    "این نشانی آی‌پی مستقیم نمی‌تواند از کلید عبور مرورگر استفاده کند. عبارت مخزن را با مدیر رمز عبور وارد کنید؛ برای باز کردن داخلی با دستگاه، نام میزبان مورد اعتماد لازم است.",
  "Opening HAVEN at a new hostname creates separate browser storage. Keep this trusted IP tab open to approve the new browser; old message history does not move automatically.":
    "باز کردن هیون با نام میزبان تازه فضای ذخیره‌سازی مرورگر جداگانه می‌سازد. این تب مورد اعتمادِ آی‌پی را برای تأیید مرورگر تازه باز نگه دارید؛ تاریخچهٔ پیام‌ها خودکار منتقل نمی‌شود.",
  "Built-in device unlock is unavailable in this browser. Keep using the vault passphrase or a password manager.":
    "باز کردن داخلی با دستگاه در این مرورگر در دسترس نیست. از عبارت مخزن یا مدیر رمز عبور استفاده کنید.",
  "Device verification may use biometrics or your device PIN. A browser profile reset, removed passkey, or lost device still requires your saved passphrase and recovery kit.":
    "تأیید دستگاه ممکن است با زیست‌سنجی یا پین دستگاه انجام شود. با پاک شدن پروفایل مرورگر، حذف کلید عبور یا گم شدن دستگاه، به عبارت ذخیره‌شده و بستهٔ بازیابی نیاز دارید.",
  "Device unlock removed. Your vault passphrase still works.":
    "باز کردن با دستگاه حذف شد. عبارت ورود مخزن همچنان کار می‌کند.",
  "Device unlock is ready. Your passphrase remains the fallback.":
    "باز کردن با دستگاه آماده است. عبارت ورود مخزن راه جایگزین می‌ماند.",
  "Could not read this browser’s device unlock settings":
    "خواندن تنظیمات باز کردن با دستگاه در این مرورگر ممکن نشد",
  "Could not change device unlock settings":
    "تغییر تنظیمات باز کردن با دستگاه ممکن نشد",
  "Working…": "در حال انجام…",
  "Decrypt and play audio": "رمزگشایی و پخش صدا",
  "Add attachment": "افزودن پیوست",
  "Choose an attachment type": "انتخاب نوع پیوست",
  "Photos & videos": "عکس و ویدیو",
  "Choose from your gallery": "انتخاب از گالری",
  Audio: "صدا",
  "Music and audio files": "موسیقی و فایل‌های صوتی",
  File: "فایل",
  "Documents and other files": "اسناد و فایل‌های دیگر",
  "Choose photos and videos": "انتخاب عکس و ویدیو",
  "Choose audio": "انتخاب صدا",
  "Choose a file": "انتخاب فایل",
  "Attachment preview": "پیش‌نمایش پیوست",
  "Preview content": "محتوای پیش‌نمایش",
  "Selected photo preview": "پیش‌نمایش عکس انتخاب‌شده",
  "Selected video preview": "پیش‌نمایش ویدیوی انتخاب‌شده",
  "Selected audio preview": "پیش‌نمایش صدای انتخاب‌شده",
  "Preparing preview…": "در حال آماده‌سازی پیش‌نمایش…",
  "Preview is not available for this file type.":
    "پیش‌نمایش این نوع فایل در دسترس نیست.",
  "Preview could not be prepared. Choose another file or send without a preview.":
    "آماده‌سازی پیش‌نمایش ممکن نشد. فایل دیگری انتخاب کنید یا بدون پیش‌نمایش بفرستید.",
  "This browser cannot preview this file. Choose another file or send without a preview.":
    "این مرورگر نمی‌تواند این فایل را نمایش دهد. فایل دیگری انتخاب کنید یا بدون پیش‌نمایش بفرستید.",
  "Choose a photo or video, or use File for other types.":
    "عکس یا ویدیو انتخاب کنید؛ برای انواع دیگر از «فایل» استفاده کنید.",
  "Choose an audio file, or use File for other types.":
    "فایل صوتی انتخاب کنید؛ برای انواع دیگر از «فایل» استفاده کنید.",
  "Chat controls": "کنترل‌های گفتگو",
  "Use the paperclip to choose Photos & videos, Audio, or File. Check the local preview before sending. Files can be up to 25 MiB.":
    "با سنجاق «عکس و ویدیو»، «صدا» یا «فایل» را انتخاب کنید. پیش از ارسال، پیش‌نمایش محلی را بررسی کنید. فایل‌ها می‌توانند تا ۲۵ مگابایت باشند.",

  "Chat details": "جزئیات گفتگو",
  "Discard recording": "حذف ضبط",
  "Filter conversations": "فیلتر گفتگوها",
  "All chats": "همهٔ گفتگوها",
  Unread: "خوانده‌نشده",
  "You’re all caught up": "همهٔ پیام‌ها را خوانده‌اید",
  "New unread messages will appear here.":
    "پیام‌های خوانده‌نشدهٔ تازه اینجا نمایش داده می‌شوند.",
  "Ordinary attachment": "فایل معمولی",
  "Remove attachment": "حذف پیوست",
  "Send attachment": "ارسال پیوست",
  "Choose a file, check its name and viewing mode, then select Send attachment. Files can be up to 25 MiB. Use the microphone to record; stop recording to send your voice note.":
    "فایل را انتخاب کنید، نام و حالت مشاهده‌اش را بررسی کنید و «ارسال پیوست» را بزنید. فایل‌ها می‌توانند تا ۲۵ مگابایت باشند. با میکروفن ضبط کنید؛ با توقف ضبط پیام صوتی فرستاده می‌شود.",

  "Message actions": "گزینه‌های پیام",
  "Copy text": "کپی متن",
  "Send a heart": "فرستادن قلب",
  "Message copied. Clipboard history may keep a copy.":
    "پیام کپی شد. ممکن است در تاریخچهٔ کلیپ‌بورد باقی بماند.",
  "Could not copy. Select the message text to copy it manually.":
    "کپی ممکن نشد. متن پیام را انتخاب و دستی کپی کنید.",
  "Messages in this conversation": "پیام‌های این گفتگو",
  "Earlier message": "پیام قبلی",
  "This message is not saved on this device.":
    "این پیام روی این دستگاه ذخیره نشده است.",
  Reactions: "واکنش‌ها",
  Today: "امروز",
  Yesterday: "دیروز",
  edited: "ویرایش‌شده",
  "New messages · jump to latest": "پیام‌های جدید · رفتن به آخر گفتگو",
  "Jump to latest": "رفتن به آخر گفتگو",
  "New messages": "پیام‌های جدید",
  "Message deleted": "پیام حذف شد",
  "Voice note": "پیام صوتی",
  Attachment: "فایل پیوست",
  "Saved on this device": "روی این دستگاه ذخیره شد",
  "Encrypting…": "در حال رمزگذاری…",
  "Queued for sending": "در صف ارسال",
  "Sent to server": "به سرور ارسال شد",
  "Synced to this device": "با این دستگاه همگام شد",
  "Could not send": "ارسال نشد",
  "Read (receipt shared)": "خوانده شد (با اشتراک رسید)",
  "Edit message": "ویرایش پیام",
  "Reply to": "پاسخ به",
  "Cancel edit": "لغو ویرایش",
  "Edit your message": "پیامتان را ویرایش کنید",
  "Write a message…": "پیام بنویسید…",
  "Add emoji": "افزودن ایموجی",
  "Choose an emoji": "انتخاب ایموجی",
  "Message composer": "نوشتن پیام",
  "Save edit": "ذخیرهٔ ویرایش",
  "Recording voice note": "در حال ضبط پیام صوتی",
  "Stop to send · up to 2 minutes": "برای ارسال ضبط را متوقف کنید · تا ۲ دقیقه",
  "Offline · messages will wait on this device until you reconnect.":
    "آفلاین · پیام‌ها تا اتصال دوباره روی این دستگاه منتظر می‌مانند.",
  "Chat tips": "راهنمای گفتگو",
  "On a computer, Enter sends and Shift + Enter adds a line. On a phone, Return adds a line; tap the arrow to send.":
    "در رایانه Enter پیام را می‌فرستد و Shift + Enter خط تازه می‌سازد. در گوشی Return خط تازه می‌سازد؛ برای ارسال پیکان را بزنید.",
  "Choosing a file sends it immediately. Use the microphone to record; stop recording to send your voice note.":
    "با انتخاب فایل، ارسال آن شروع می‌شود. با میکروفن ضبط کنید؛ با توقف ضبط، پیام صوتی فرستاده می‌شود.",
  "One check means the server accepted your message. A read indicator appears only when a participant shares a read receipt.":
    "یک تیک یعنی سرور پیام را پذیرفته است. نشان خواندن فقط وقتی نمایش داده می‌شود که یکی از افراد رسید خواندن را به اشتراک بگذارد.",
  "Search and drafts stay on this device. Copied messages can remain in clipboard history.":
    "جستجو و پیش‌نویس‌ها روی این دستگاه می‌مانند. پیام‌های کپی‌شده ممکن است در تاریخچهٔ کلیپ‌بورد باقی بمانند.",
  "Open video": "باز کردن ویدیو",
  "Open photo": "باز کردن عکس",
  "Video preview": "نمایش ویدیو",
  "Photo preview": "نمایش عکس",
  "Close preview": "بستن نمایش",
  "Shared photo": "عکس اشتراک‌گذاشته‌شده",
  "Decrypt on this device": "رمزگشایی روی این دستگاه",
  "Decrypting media on this device…": "در حال رمزگشایی فایل روی این دستگاه…",
  "Media unavailable or integrity check failed. Close and try again.":
    "فایل در دسترس نیست یا بررسی صحت آن ناموفق بود. ببندید و دوباره تلاش کنید.",
  "Download options": "گزینه‌های دانلود",
  Participant: "عضو گفتگو",
  "Say hello": "سلام کنید",
  "No matching conversations": "گفتگوی مطابقی پیدا نشد",
  "Try a name or a word from a message on this device.":
    "نام یا کلمه‌ای از پیام‌های روی این دستگاه را جستجو کنید.",
  "Search this conversation": "جستجو در این گفتگو",
  "Close search": "بستن جستجو",
  results: "نتیجه",
  "Browser approval needed": "تأیید مرورگر لازم است",
  "End-to-end encrypted": "رمزگذاری سرتاسری",
  "Security code comparison needed": "مقایسهٔ کد امنیتی لازم است",
  "Unlock this browser to write a message.":
    "برای نوشتن پیام این مرورگر را باز کنید.",
  "Approve this browser before messaging.":
    "پیش از پیام دادن، این مرورگر را تأیید کنید.",
  "Compare security codes above to start chatting.":
    "برای شروع گفتگو، کدهای امنیتی بالا را مقایسه کنید.",
  "Messaging is unavailable until security qualification is complete.":
    "تا تکمیل ارزیابی امنیتی، پیام‌رسانی در دسترس نیست.",
  "Send a message, share a photo, or record a voice note.":
    "پیامی بنویسید، عکسی بفرستید یا یک پیام صوتی ضبط کنید.",
  "Delete this message for the conversation? Recipients may already have saved a copy.":
    "این پیام برای گفتگو حذف شود؟ ممکن است گیرندگان قبلاً نسخه‌ای ذخیره کرده باشند.",
  "This browser is still waiting for approval. Use an already approved browser to follow the steps below, then check again.":
    "این مرورگر هنوز منتظر تأیید است. مراحل زیر را در مرورگر از پیش تأییدشده انجام دهید و دوباره بررسی کنید.",
  "You’re signed in. One more step protects your messages: a browser already approved for your account must approve this one.":
    "وارد حساب شده‌اید. برای محافظت از پیام‌هایتان یک مرحله مانده است: مرورگری که قبلاً برای حسابتان تأیید شده باید این مرورگر را تأیید کند.",
  "Already approved for your account": "مرورگرهای تأییدشدهٔ حساب شما",
  "Open your approved browser": "مرورگر تأییدشده‌تان را باز کنید",
  "Visit this same HAVEN address in that browser and unlock its existing vault.":
    "در آن مرورگر همین نشانی هیون را باز کنید و مخزن موجود آن را باز کنید.",
  "Compare this browser’s security code": "کد امنیتی این مرورگر را مقایسه کنید",
  "In People & trust on the approved browser, find this browser, compare the full code below, and choose Verify fingerprint.":
    "در بخش «افراد و اعتماد» مرورگر تأییدشده، این مرورگر را پیدا کنید، همهٔ کد زیر را مقایسه کنید و «تأیید اثر انگشت» را بزنید.",
  "Approve, then come back here": "تأیید کنید و به اینجا برگردید",
  "In Devices on the approved browser, choose Approve enrollment for this browser. Then return here and choose Check approval.":
    "در بخش «دستگاه‌ها» مرورگر تأییدشده، «تأیید ثبت دستگاه» را برای این مرورگر بزنید. سپس به اینجا برگردید و «بررسی تأیید» را بزنید.",
  "This browser’s security code": "کد امنیتی این مرورگر",
  "This code identifies this browser. Compare all of it; it is not a password to enter.":
    "این کد شناسهٔ این مرورگر است. همهٔ آن را مقایسه کنید؛ رمز عبوری برای وارد کردن نیست.",
  "I can’t access the approved browser": "به مرورگر تأییدشده دسترسی ندارم",
  "Keep this browser’s vault. Creating another vault will not approve this browser or recover the old keys.":
    "مخزن این مرورگر را نگه دارید. ساخت مخزن تازه نه این مرورگر را تأیید می‌کند و نه کلیدهای قبلی را برمی‌گرداند.",
  "No account recovery method is configured. You need the original approved browser to continue with this identity. An administrator cannot approve it using an account password.":
    "روش بازیابی حساب تنظیم نشده است. برای ادامه با این هویت به مرورگر اصلی تأییدشده نیاز دارید. مدیر نمی‌تواند با رمز حساب آن را تأیید کند.",
  "If you previously saved a recovery kit, use account recovery from the sign-in screen in a separate browser profile. Recovery replaces the identity and requires your contacts to verify the new one.":
    "اگر قبلاً کیت بازیابی ذخیره کرده‌اید، در پروفایل مرورگر جداگانه از بازیابی حساب در صفحهٔ ورود استفاده کنید. بازیابی هویت را جایگزین می‌کند و مخاطبان باید هویت تازه را تأیید کنند.",
  "If this was a test account and the original browser is gone, ask for a new invitation and create a separate account. This does not restore the old messages.":
    "اگر این حساب آزمایشی بود و مرورگر اصلی دیگر در دسترس نیست، دعوت‌نامهٔ تازه بگیرید و حساب جداگانه بسازید. این کار پیام‌های قبلی را بازیابی نمی‌کند.",

  "Show or copy the passphrase before confirming you saved it.":
    "پیش از تأیید ذخیره، عبارت ورود را نمایش دهید یا کپی کنید.",
  "Generate a secure passphrase": "ساخت عبارت ورود امن",
  "Save your generated passphrase": "عبارت ورود ساخته‌شده را ذخیره کنید",
  "This passphrase unlocks only this browser’s vault. Save it in your password manager or write it down somewhere private.":
    "این عبارت فقط مخزن همین مرورگر را باز می‌کند. آن را در مدیر رمز عبور ذخیره کنید یا در جایی خصوصی یادداشت کنید.",
  "Generated passphrase": "عبارت ورود ساخته‌شده",
  "Passphrase hidden": "عبارت ورود پنهان است",
  "Hide passphrase": "پنهان کردن عبارت",
  "Show passphrase": "نمایش عبارت",
  "Copying…": "در حال کپی…",
  "Copy passphrase": "کپی عبارت ورود",
  "Passphrase copied. Save it privately before continuing.":
    "عبارت ورود کپی شد. پیش از ادامه آن را در جایی خصوصی ذخیره کنید.",
  "Automatic copying is unavailable. Choose Show passphrase to select and copy it, or write it down privately.":
    "کپی خودکار در دسترس نیست. برای انتخاب و کپی عبارت، «نمایش عبارت» را بزنید یا آن را در جایی خصوصی یادداشت کنید.",
  "Clipboard history or sync may retain a copy. HAVEN does not send this passphrase to the server.":
    "تاریخچه یا همگام‌سازی کلیپ‌بورد ممکن است نسخه‌ای نگه دارد. هیون این عبارت را به سرور نمی‌فرستد.",
  "I’ve saved my passphrase somewhere private":
    "عبارت ورودم را در جایی خصوصی ذخیره کرده‌ام",
  "Generate another": "ساخت عبارت دیگر",
  "Use my own passphrase": "عبارت خودم را وارد می‌کنم",
  "Save your generated passphrase and confirm before continuing":
    "پیش از ادامه، عبارت ورود ساخته‌شده را ذخیره و تأیید کنید",
  "Secure passphrase generation is unavailable. Enter your own passphrase or try another trusted browser.":
    "ساخت امن عبارت ورود در دسترس نیست. عبارت خودتان را وارد کنید یا مرورگر مورد اعتماد دیگری را امتحان کنید.",

  You: "شما",
  "Start a chat": "شروع گفتگو",
  "Set up this browser": "آماده‌سازی این مرورگر",
  "Unlock this browser": "باز کردن این مرورگر",
  "Your private keys are already saved here. Unlock them to continue.":
    "کلیدهای خصوصی شما در این مرورگر ذخیره شده‌اند. برای ادامه مخزن را باز کنید.",
  "Choose an unlock passphrase to protect your messages on this browser. It stays on this device and must differ from your account password.":
    "برای محافظت از پیام‌ها در این مرورگر یک عبارت ورود انتخاب کنید. این عبارت روی همین دستگاه می‌ماند و باید با رمز حساب شما متفاوت باشد.",
  "Unlock passphrase": "عبارت ورود مخزن",
  "Confirm unlock passphrase": "تکرار عبارت ورود مخزن",
  "Use at least 20 characters. A few unrelated words are easier to remember.":
    "حداقل ۲۰ نویسه استفاده کنید. به خاطر سپردن چند واژهٔ نامرتبط ساده‌تر است.",
  "Preparing this browser…": "در حال آماده‌سازی مرورگر…",
  "Unlock and continue": "باز کردن و ادامه",
  "Set up and continue": "آماده‌سازی و ادامه",
  "Keep a recovery kit after setup. Clearing browser data can permanently remove your keys.":
    "پس از آماده‌سازی یک بستهٔ بازیابی نگه دارید. پاک کردن داده‌های مرورگر می‌تواند کلیدها را برای همیشه حذف کند.",
  "The unlock passphrases do not match": "عبارت‌های ورود مخزن یکسان نیستند",
  "Browser storage is unavailable. Keep your existing data and try again.":
    "فضای ذخیره‌سازی مرورگر در دسترس نیست. داده‌های فعلی را نگه دارید و دوباره تلاش کنید.",
  "Messaging is unavailable until security qualification is complete. An administrator cannot bypass this gate.":
    "پیام‌رسانی تا تکمیل ارزیابی امنیتی در دسترس نیست. مدیر نیز نمی‌تواند این محدودیت را دور بزند.",
  "Your friend’s invitation": "دعوت‌نامهٔ دوست شما",
  "Your friend link": "پیوند دوستی شما",
  "Send this link privately. It creates one account, expires in 24 hours, and helps your friend connect with you.":
    "این پیوند را خصوصی بفرستید. برای ساخت یک حساب است، پس از ۲۴ ساعت منقضی می‌شود و دوستتان را به شما متصل می‌کند.",
  "Share this with someone who already has a HAVEN account. They can connect without typing a device ID.":
    "این پیوند را برای کسی بفرستید که حساب هیون دارد. او بدون وارد کردن شناسهٔ دستگاه به شما متصل می‌شود.",
  "Link to share": "پیوند برای اشتراک‌گذاری",
  "Copy link": "کپی پیوند",
  "Link copied": "پیوند کپی شد",
  "Select and copy the link above": "پیوند بالا را انتخاب و کپی کنید",
  "Friend link QR code": "کد کیوآر پیوند دوستی",
  "Revoke this invitation": "لغو این دعوت‌نامه",
  "Compare your friend’s security code": "کد امنیتی دوستتان را مقایسه کنید",
  "Ask your friend to open Start a chat → My security code. Compare the entire code in person or through another trusted channel. A link by itself does not verify who sent it.":
    "از دوستتان بخواهید «شروع گفتگو ← کد امنیتی من» را باز کند. همهٔ کد را حضوری یا از راهی قابل اعتماد مقایسه کنید. پیوند به‌تنهایی هویت فرستنده را تأیید نمی‌کند.",
  "This friend’s key changed. Stop and verify the change in People & trust. This guide will not replace an existing identity.":
    "کلید دوستتان تغییر کرده است. ادامه ندهید و تغییر را در «افراد و اعتماد» بررسی کنید. این راهنما هویت قبلی را جایگزین نمی‌کند.",
  "Friend’s name": "نام دوست",
  "I compared the entire code with my friend through another trusted channel":
    "همهٔ کد را از راهی قابل اعتماد با دوستم مقایسه کردم",
  "Connecting…": "در حال اتصال…",
  "Verify and continue": "تأیید و ادامه",
  "This browser is ready": "این مرورگر آماده است",
  "This browser needs approval": "این مرورگر نیاز به تأیید دارد",
  "Approve this browser from a trusted device":
    "این مرورگر را از دستگاه مورد اعتماد تأیید کنید",
  "Keep this vault. Open Devices on a browser you already trust, compare this browser’s fingerprint, and approve its enrollment. Your keys will not be replaced.":
    "این مخزن را نگه دارید. در مرورگر مورد اعتماد، «دستگاه‌ها» را باز کنید، اثر انگشت این مرورگر را مقایسه کنید و ثبت آن را تأیید کنید. کلیدها جایگزین نمی‌شوند.",
  "Check approval": "بررسی تأیید",
  "Open device details": "باز کردن جزئیات دستگاه",
  "Local evaluation only: this address works on this computer. A friend on another device needs a reachable server with trusted HTTPS.":
    "فقط ارزیابی محلی: این آدرس روی همین رایانه کار می‌کند. دوستتان روی دستگاه دیگر به سروری قابل دسترس با HTTPS معتبر نیاز دارد.",
  "Back to connection options": "بازگشت به گزینه‌های اتصال",
  "Who would you like to talk to?": "با چه کسی می‌خواهید گفتگو کنید؟",
  "Invite a friend to join, or use the friend link they shared with you. You will compare security codes before chatting.":
    "دوستی را دعوت کنید یا پیوند دوستی او را وارد کنید. پیش از گفتگو کدهای امنیتی را مقایسه خواهید کرد.",
  "Invite a friend": "دعوت از یک دوست",
  "I have a friend link": "پیوند دوستی دارم",
  "Share my friend link": "اشتراک‌گذاری پیوند دوستی من",
  "Signup invitations left today: {count}":
    "دعوت‌نامه‌های باقی‌ماندهٔ امروز: {count}",
  "Connect with your friend": "اتصال به دوست شما",
  "Friend link": "پیوند دوستی",
  "Checking link…": "بررسی پیوند…",
  "My security code": "کد امنیتی من",
  "Your friend compares this code with the one shown for you on their browser.":
    "دوستتان این کد را با کدی که برای شما در مرورگرش می‌بیند مقایسه می‌کند.",
  "Manage pending invitations": "مدیریت دعوت‌نامه‌های باز",
  "Advanced conversation tools": "ابزارهای پیشرفتهٔ گفتگو",
  "Use manual group creation or device details only when you need them. The guided flow above creates a private chat for you.":
    "ساخت دستی گروه و جزئیات دستگاه برای نیازهای پیشرفته است. راهنمای بالا یک گفتگوی خصوصی برای شما می‌سازد.",
  "Create conversation manually": "ساخت دستی گفتگو",
  "The administrator has paused new invitations. You can still connect with someone who already has an account.":
    "مدیر دعوت‌نامه‌های جدید را متوقف کرده است. همچنان می‌توانید با کسی که حساب دارد متصل شوید.",
  "Ask the administrator for a signup invitation. You can still share a friend link with an existing member.":
    "از مدیر دعوت‌نامهٔ عضویت بخواهید. همچنان می‌توانید پیوند دوستی را برای عضو فعلی بفرستید.",
  "Today’s invitation limit has been reached. Try again after the daily reset.":
    "سهمیهٔ دعوت امروز تمام شده است. پس از بازنشانی روزانه دوباره تلاش کنید.",
  "You already have three pending invitations. Revoke one before creating another.":
    "سه دعوت‌نامهٔ باز دارید. پیش از ساخت دعوت جدید یکی را لغو کنید.",
  "Finish approving this browser before inviting a friend.":
    "پیش از دعوت از دوست، تأیید این مرورگر را تکمیل کنید.",
  "Could not check this browser. Reconnect and try again.":
    "بررسی مرورگر ممکن نشد. متصل شوید و دوباره تلاش کنید.",
  "Could not check the security code. Reconnect and try again.":
    "بررسی کد امنیتی ممکن نشد. متصل شوید و دوباره تلاش کنید.",
  "Could not check this conversation. Reconnect and try again.":
    "بررسی گفتگو ممکن نشد. متصل شوید و دوباره تلاش کنید.",
  "A conversation needs security-code verification. Open it to continue.":
    "یک گفتگو نیاز به تأیید کد امنیتی دارد. برای ادامه آن را باز کنید.",
  "This is one of your own browsers. Share your link with your friend instead.":
    "این یکی از مرورگرهای خودتان است. پیوندتان را برای دوستتان بفرستید.",
  "This friend’s browser is no longer approved. Ask for a new friend link.":
    "مرورگر دوستتان دیگر تأییدشده نیست. پیوند دوستی تازه‌ای بخواهید.",
  "The security code does not match this link. Stop and ask your friend for a new link.":
    "کد امنیتی با این پیوند مطابقت ندارد. ادامه ندهید و پیوند تازه‌ای بخواهید.",
  "Verify to start": "برای شروع تأیید کنید",
  "Disable member invitations": "غیرفعال کردن دعوت توسط اعضا",
  "Enable member invitations": "فعال کردن دعوت توسط اعضا",
  "Connection could not finish": "اتصال کامل نشد",
  "Browser setup could not finish": "آماده‌سازی مرورگر کامل نشد",
  "This friend link belongs to a different server. Use an independently trusted server address.":
    "این پیوند متعلق به سرور دیگری است. از آدرس سروری استفاده کنید که مستقل تأییدش کرده‌اید.",
  "Paste a complete HAVEN friend link": "پیوند کامل دوستی هیون را وارد کنید",
  "This friend link is invalid or uses an unsupported version":
    "این پیوند نامعتبر است یا نسخهٔ آن پشتیبانی نمی‌شود",
  "This friend link is too long": "این پیوند دوستی بیش از حد طولانی است",
  "Invitations are unavailable": "دعوت‌نامه‌ها در دسترس نیستند",
  "Checking this browser…": "بررسی این مرورگر…",

  "What stays on the server": "چه چیزی روی سرور باقی می‌ماند",
  "Messages and files are encrypted on your device. The server does not hold your message decryption keys.":
    "پیام‌ها و فایل‌ها روی دستگاه شما رمز می‌شوند. سرور کلید رمزگشایی پیام‌های شما را ندارد.",
  "Retention policy unavailable. Reconnect to check the server settings.":
    "سیاست نگهداری در دسترس نیست. برای بررسی تنظیمات سرور دوباره متصل شوید.",
  "Try again": "تلاش دوباره",
  "Loading retention policy…": "دریافت سیاست نگهداری…",
  "Delivered messages": "پیام‌های تحویل‌شده",
  "Encrypted payloads are removed after every eligible active device syncs, with a {hours}-hour retry window.":
    "محتوای رمز‌شده پس از همگام‌سازی همهٔ دستگاه‌های فعال واجد شرایط و مهلت تلاش مجدد {hours} ساعته حذف می‌شود.",
  "Offline recipients": "گیرنده‌های آفلاین",
  "Undelivered encrypted messages stay available. Keep a recovery kit: the server cannot rebuild a lost vault.":
    "پیام‌های رمز‌شدهٔ همگام‌نشده باقی می‌مانند. بستهٔ بازیابی را نگه دارید؛ سرور نمی‌تواند مخزن ازدست‌رفته را بازسازی کند.",
  "Files and voice notes": "فایل‌ها و پیام‌های صوتی",
  "Available for up to {days} days. View-once files are removed sooner after all openings finish.":
    "حداکثر {days} روز در دسترس‌اند. فایل‌های یک‌بار مشاهده پس از پایان همهٔ نوبت‌ها زودتر حذف می‌شوند.",
  "Security records": "سوابق امنیتی",
  "Security audit records expire after {days} days. Expired sessions and used invitations are cleaned automatically.":
    "سوابق ممیزی امنیتی پس از {days} روز حذف می‌شوند. نشست‌های منقضی و دعوت‌های استفاده‌شده خودکار پاک می‌شوند.",
  "Understand the remaining limits": "محدودیت‌های باقی‌مانده",
  "Accounts, public device keys, conversation membership and signed delivery proofs remain visible to the server. This is not anonymous messaging.":
    "حساب‌ها، کلیدهای عمومی دستگاه‌ها، عضویت گفتگو و گواهی‌های امضاشدهٔ تحویل برای سرور قابل مشاهده‌اند. این پیام‌رسان ناشناس نیست.",
  "The connection server can see your IP while you connect. Request logs are disabled in the supplied deployment; a compromised host can still observe traffic.":
    "سرور اتصال هنگام اتصال آی‌پی شما را می‌بیند. ثبت درخواست‌ها در پیکربندی ارائه‌شده خاموش است؛ میزبان نفوذشده همچنان می‌تواند ترافیک را ببیند.",
  "Deletion removes live database records, not copies in older backups, replicas or recipients’ devices. Cleanup runs periodically.":
    "حذف، سوابق پایگاه دادهٔ فعال را پاک می‌کند؛ نسخه‌های پشتیبان قدیمی، رونوشت‌ها و دستگاه گیرنده را پاک نمی‌کند. پاک‌سازی دوره‌ای است.",
  "A compromised website can serve altered browser code that steals keys when you unlock. Independent security review is still pending.":
    "وب‌سایت نفوذشده می‌تواند کد تغییریافته‌ای ارائه دهد که هنگام باز کردن مخزن کلیدها را بدزدد. بررسی امنیتی مستقل هنوز انجام نشده است.",
  "Open your vault": "ورود به مخزن شما",
  "Appearance & privacy": "ظاهر و حریم خصوصی",
  "No matching messages": "پیامی با این عبارت پیدا نشد",
  "A fresh start. Say hello.": "شروعی تازه. سلام کنید.",
  "Try another word. Search only covers messages saved on this device.":
    "واژهٔ دیگری را امتحان کنید. جستجو فقط پیام‌های ذخیره‌شده در این دستگاه را در بر می‌گیرد.",
  "Messages you can read on this device will appear here.":
    "پیام‌های قابل خواندن در این دستگاه اینجا نمایش داده می‌شوند.",
  "Main navigation": "ناوبری اصلی",
  "Skip to content": "رفتن به محتوا",
  "Switch to dark mode": "تغییر به حالت تیره",
  "Switch to light mode": "تغییر به حالت روشن",
  Details: "جزئیات",
  More: "بیشتر",
  Close: "بستن",
  "Your space": "فضای شما",
  "Opening is recorded to enforce the limit, even with read receipts off.":
    "برای اجرای محدودیت، باز شدن ثبت می‌شود؛ حتی اگر رسید خواندن خاموش باشد.",
  "View once": "یک‌بار مشاهده",
  "View once photos and videos": "عکس و ویدیوی یک‌بار مشاهده",
  "No reopening in HAVEN. Recipients can still capture the screen. One view per person across devices.":
    "بازگشایی در هیون ممکن نیست؛ گیرنده همچنان می‌تواند از صفحه تصویر بگیرد. هر نفر در مجموع همهٔ دستگاه‌هایش یک‌بار می‌بیند.",
  "View once supports photos and videos only":
    "یک‌بار مشاهده فقط برای عکس و ویدیو پشتیبانی می‌شود",
  "View-once media queued": "رسانهٔ یک‌بار مشاهده در صف ارسال است",
  "View-once media not sent": "رسانهٔ یک‌بار مشاهده ارسال نشد",
  "View-once media sent": "رسانهٔ یک‌بار مشاهده ارسال شد",
  Opened: "باز شده",
  "View-once media unavailable": "رسانهٔ یک‌بار مشاهده در دسترس نیست",
  "Open video once": "یک‌بار باز کردن ویدیو",
  "Open photo once": "یک‌بار باز کردن عکس",
  "Video · view once": "ویدیو · یک‌بار مشاهده",
  "Photo · view once": "عکس · یک‌بار مشاهده",
  "Opening uses your one view, even if interrupted. Stay online.":
    "با باز کردن، فرصت مشاهده مصرف می‌شود؛ حتی اگر قطع شود. آنلاین بمانید.",
  "View-once video": "ویدیوی یک‌بار مشاهده",
  "View-once photo": "عکس یک‌بار مشاهده",
  "Close view-once media": "بستن رسانهٔ یک‌بار مشاهده",
  "Opening encrypted media…": "در حال باز کردن رسانهٔ رمزگذاری‌شده…",
  "This view was consumed. It cannot be opened again, even if loading was interrupted.":
    "فرصت مشاهده مصرف شد. حتی اگر بارگیری قطع شده باشد، بازگشایی ممکن نیست.",
  "Could not open media. No media was displayed.":
    "رسانه باز نشد. هیچ رسانه‌ای نمایش داده نشد.",
  "Closes when you leave or after 10 minutes. Screen capture cannot be prevented.":
    "با خروج یا پس از ۱۰ دقیقه بسته می‌شود. جلوگیری از تصویربرداری صفحه ممکن نیست.",
  "A little closer, wherever you are.": "هر جا باشید، کمی نزدیک‌تر.",
  "Private group": "گروه خصوصی",
  "Direct conversation": "گفتگوی مستقیم",
  "Unlock this device to find your conversations.":
    "برای دیدن گفتگوها، مخزن این دستگاه را باز کنید.",
  "Start a conversation and invite a verified device. Your messages stay between you.":
    "گفتگویی بسازید و یک دستگاه تأییدشده را دعوت کنید. پیام‌ها بین خودتان می‌مانند.",
  "Search stays on this device": "جستجو فقط در همین دستگاه است",
  "Back to conversations": "بازگشت به گفتگوها",
  "Keys stay on your devices": "کلیدها در دستگاه‌های شما می‌مانند",
  "Cancel reply": "لغو پاسخ",
  "Your people. Your space.": "آدم‌های شما. فضای شما.",
  "Make yourself at home.": "به فضای خودتان خوش آمدید.",
  "Pick a conversation or start something new. A quieter way to stay close to the people who matter.":
    "گفتگویی را انتخاب کنید یا گفتگوی تازه‌ای بسازید. راهی آرام‌تر برای نزدیک ماندن به آدم‌های مهم زندگی‌تان.",
  "Unlock your private space to reconnect with your people. Your keys stay right here, on this device.":
    "فضای خصوصی‌تان را باز کنید و به دوستانتان بپیوندید. کلیدهای شما همین‌جا، در این دستگاه می‌مانند.",
  "Set up this device": "آماده‌سازی این دستگاه",
  "Find your people": "پیدا کردن دوستان",
  "How HAVEN works": "هیون چگونه کار می‌کند",
  "Invite-only community": "جمعی فقط با دعوت",

  "Online indicators": "نشانگرهای اتصال افراد",
  "Another participant has a reachable active tab (server hint)":
    "برگهٔ فعال یکی از اعضا در دسترس است؛ نشانه‌ای از سرور، نه اثبات حضور یا خواندن پیام",
  "Vault locked locally. Server session revocation is unconfirmed; sign in again when connected to revoke sessions.":
    "مخزن در این دستگاه قفل شد. لغو نشست در سرور تأیید نشده است؛ پس از اتصال دوباره وارد شوید و نشست‌ها را لغو کنید.",
  "Revoked device: verify historical signatures only. This does not authorize new membership.":
    "دستگاه لغوشده: فقط برای بررسی امضاهای تاریخی تأیید کنید. این کار مجوز عضویت جدید نمی‌دهد.",
  "Clear partial download": "پاک کردن بارگیری نیمه‌تمام",
  "Experimental cryptographic integration. Not approved for production use.":
    "یکپارچگی رمزنگاری محلی بدون بازبینی مستقل است. برای استفادهٔ عملیاتی تأیید نشده است.",
  "Clear delivered local history": "پاک کردن تاریخچهٔ محلی تحویل‌شده",
  "Permanently clear delivered local history and drafts? Export a recovery kit first. Pending sends and live device keys are preserved.":
    "تاریخچهٔ محلی تحویل‌شده و پیش‌نویس‌ها برای همیشه پاک شوند؟ ابتدا بستهٔ بازیابی تهیه کنید. پیام‌های در انتظار و کلیدهای فعال دستگاه حفظ می‌شوند.",
  "[deleted]": "[حذف‌شده]",
  "read receipt (opt-in)": "رسید خواندن (اختیاری)",
  "Private community": "جامعهٔ خصوصی",
  Messages: "پیام‌ها",
  "People & trust": "افراد و اعتماد",
  Devices: "دستگاه‌ها",
  "Recovery kit": "بستهٔ بازیابی",
  Settings: "تنظیمات",
  "Operator console": "کنسول مدیریت",
  "Connection & help": "اتصال و راهنما",
  "Log out": "خروج",
  "Lock vault": "قفل کردن مخزن",
  "Connected to primary": "متصل به سرور اصلی",
  "Not connected": "متصل نیست",
  Reconnecting: "اتصال دوباره",
  "Crypto verification needed": "تأیید رمزنگاری لازم است",
  "Key state locked": "کلیدها قفل هستند",
  "Messages pending": "پیام‌های در انتظار",
  "Security qualification pending": "ارزیابی امنیتی تکمیل نشده است",
  "Sign in": "ورود",
  "Create account": "ساخت حساب",
  Username: "نام کاربری",
  Password: "گذرواژه",
  "Display name": "نام نمایشی",
  "Invitation token": "توکن دعوت",
  "Invite only. No phone number, email, or external login.":
    "فقط با دعوت. بدون شماره تلفن، ایمیل یا ورود خارجی.",
  "Open your private space": "ورود به فضای خصوصی",
  "A quiet place to stay connected.": "جایی آرام برای در ارتباط ماندن.",
  "Use a trusted HTTPS IP address. Never bypass a certificate warning.":
    "از نشانی IP با HTTPS معتبر استفاده کنید. هشدار گواهی را دور نزنید.",
  Conversations: "گفتگوها",
  "New conversation": "گفتگوی جدید",
  "Search on this device": "جستجو در همین دستگاه",
  "No conversations yet": "هنوز گفتگویی ندارید",
  "Your conversations will appear here after the cryptographic integration is qualified.":
    "گفتگوها پس از ارزیابی یکپارچگی رمزنگاری در اینجا نمایش داده می‌شوند.",
  "Choose a conversation": "یک گفتگو انتخاب کنید",
  Message: "پیام",
  Send: "ارسال",
  "Attach file": "پیوست فایل",
  "Record voice note": "ضبط پیام صوتی",
  "Stop recording": "پایان ضبط",
  Cancel: "لغو",
  "Group & members": "گروه و اعضا",
  Direct: "مستقیم",
  Group: "گروه",
  Create: "ایجاد",
  "Local unlock passphrase": "عبارت عبور محلی",
  "Unlock vault": "باز کردن مخزن",
  "Create device vault": "ساخت مخزن دستگاه",
  "Device label": "نام دستگاه",
  "Browser storage can be erased or evicted. A server password cannot restore your keys.":
    "حافظهٔ مرورگر ممکن است پاک شود. گذرواژهٔ سرور کلیدها را بازیابی نمی‌کند.",
  "Compare this fingerprint through an independent channel before verifying.":
    "پیش از تأیید، این اثر انگشت را از کانالی مستقل مقایسه کنید.",
  "Verify fingerprint": "تأیید اثر انگشت",
  Fingerprint: "اثر انگشت",
  "Device ID": "شناسهٔ دستگاه",
  "Approve enrollment": "تأیید ثبت دستگاه",
  "Revoke device": "لغو دستگاه",
  "No devices enrolled": "دستگاهی ثبت نشده است",
  "Download encrypted kit": "دانلود بستهٔ رمزگذاری‌شده",
  "Restore encrypted kit": "بازیابی بستهٔ رمزگذاری‌شده",
  "Recovery key": "کلید بازیابی",
  "Store the key separately from the encrypted kit. Losing both permanently loses local history.":
    "کلید را جدا از بسته نگه دارید. از دست دادن هر دو، تاریخچهٔ محلی را برای همیشه از بین می‌برد.",
  Theme: "پوسته",
  Dark: "تیره",
  Light: "روشن",
  Language: "زبان",
  Notifications: "اعلان‌ها",
  "Read receipts": "رسید خواندن",
  "Typing indicators": "نشانگر تایپ",
  "Off by default": "پیش‌فرض خاموش",
  "Change password": "تغییر گذرواژه",
  "Current password": "گذرواژهٔ فعلی",
  "New password": "گذرواژهٔ جدید",
  "Log out all sessions": "خروج از همهٔ نشست‌ها",
  Invitations: "دعوت‌ها",
  "Create invitation": "ساخت دعوت",
  Revoke: "لغو",
  Accounts: "حساب‌ها",
  Suspend: "تعلیق",
  Activate: "فعال‌سازی",
  "System status": "وضعیت سیستم",
  Refresh: "تازه‌سازی",
  "No decrypted message access": "بدون دسترسی به پیام رمزگشایی‌شده",
  "Certificate trust": "اعتماد به گواهی",
  "Connection guide": "راهنمای اتصال",
  "Local only": "فقط محلی",
  Reply: "پاسخ",
  Edit: "ویرایش",
  Delete: "حذف",
  React: "واکنش",
  Save: "ذخیره",
  "Confirm fingerprint": "تأیید اثر انگشت",
  "Encryption is unavailable until the integrated security gates pass.":
    "رمزگذاری تا عبور از آزمون‌های امنیتی یکپارچه در دسترس نیست.",
  "Unsupported browser": "مرورگر پشتیبانی نمی‌شود",
  "Server password and vault passphrase must be different.":
    "گذرواژهٔ سرور و عبارت عبور مخزن باید متفاوت باشند.",
  "Group title": "عنوان گروه",
  "Verified devices only": "فقط دستگاه‌های تأییدشده",
  Download: "دانلود",
  "No server-side message search": "بدون جستجوی پیام روی سرور",
  Status: "وضعیت",
  Name: "نام",
  Role: "نقش",
  Back: "بازگشت",
  Continue: "ادامه",
  "Message keys stay on this device.":
    "کلیدهای پیام روی این دستگاه باقی می‌مانند.",
  Maintenance: "نگهداری",
  "Add member": "افزودن عضو",
  "Remove member": "حذف عضو",
  "Leave group": "ترک گروه",
  "Connection lost. Encrypted pending messages remain on this device.":
    "اتصال قطع است. پیام‌های رمزگذاری‌شده در این دستگاه می‌مانند.",
  "Recovery cannot restore state newer than the kit. Stop and reconcile before sending.":
    "بازیابی نمی‌تواند وضعیت جدیدتر از بسته را بازگرداند. پیش از ارسال، وضعیت را تطبیق دهید.",
  "Verification QR code": "رمزینهٔ تأیید هویت",
  "Decrypt and play voice note": "رمزگشایی و پخش پیام صوتی",
  "Dismiss error": "بستن خطا",
  "No route means no remote delivery. A compromised application origin can deliver code that exposes client secrets.":
    "بدون مسیر شبکه، پیام از راه دور تحویل نمی‌شود. نفوذ به مبدأ برنامه می‌تواند کدی برای افشای اسرار دستگاه ارسال کند.",
  "Conversation type": "نوع گفتگو",
  "· epoch": "· دورهٔ کلید",
  unread: "خوانده‌نشده",
  Epoch: "دورهٔ کلید",
  "Leave conversation": "ترک گفتگو",
  "Refresh cryptographic epoch": "تازه‌سازی دورهٔ رمزنگاری",
  "Cancel pending membership request and check state":
    "لغو درخواست عضویت معلق و بررسی وضعیت",
  "Transfer ownership": "انتقال مالکیت",
  "Make moderator": "تعیین مدیر گروه",
  "Review recipients and resend": "بررسی گیرندگان و ارسال دوباره",
  "Another participant is typing…": "یکی از اعضا در حال نوشتن است…",
  "— encrypted upload pending": "— بارگذاری رمزگذاری‌شده در انتظار",
  "Resume encrypted upload": "ادامهٔ بارگذاری رمزگذاری‌شده",
  "Look up a known device": "یافتن دستگاه با شناسهٔ معلوم",
  "Identity key changed. Stop and independently verify this device before continuing.":
    "کلید هویت تغییر کرده است. پیش از ادامه، توقف کنید و این دستگاه را از کانالی مستقل تأیید کنید.",
  "Recovered local history": "تاریخچهٔ محلی بازیابی‌شده",
  "These conversations belong to your previous device. Their MLS state is never resumed.":
    "این گفتگوها متعلق به دستگاه قبلی شما هستند. وضعیت MLS آن‌ها هرگز از سر گرفته نمی‌شود.",
  "Recovery restores saved history only. A fresh device and explicit peer verification are required.":
    "بازیابی فقط تاریخچهٔ ذخیره‌شده را برمی‌گرداند. دستگاه تازه و تأیید صریح مخاطبان لازم است.",
  "New account password after security reset":
    "گذرواژهٔ جدید حساب پس از بازنشانی امنیت",
  "Recovery always creates a fresh MLS identity and revokes old devices. Keep the kit and its separate key secure. Enter a new unlock secret on the Devices screen first.":
    "بازیابی همیشه هویت MLS تازه ایجاد می‌کند و دستگاه‌های قبلی را لغو می‌کند. بسته و کلید جداگانهٔ آن را امن نگه دارید. ابتدا در صفحهٔ دستگاه‌ها یک عبارت عبور تازه وارد کنید.",
  "Device ID:": "شناسهٔ دستگاه:",
  "Complete approved device enrollment": "تکمیل ثبت دستگاه تأییدشده",
  "Local data and account": "داده‌های محلی و حساب",
  "Export decrypted local history": "دریافت تاریخچهٔ محلی رمزگشایی‌شده",
  "Create an encrypted recovery kit": "ساخت بستهٔ بازیابی رمزگذاری‌شده",
  "Disabling your account revokes every session and device and pauses group delivery until authorized MLS removal. Recipients retain their copies. Ciphertext and opaque audit records follow retention policy.":
    "غیرفعال‌سازی حساب، همهٔ نشست‌ها و دستگاه‌ها را لغو کرده و تحویل گروه را تا حذف مجاز MLS متوقف می‌کند. نسخه‌های گیرندگان باقی می‌ماند. متن رمز و سوابق ممیزی تابع سیاست نگهداری هستند.",
  "Confirm password to disable account": "تأیید گذرواژه برای غیرفعال‌سازی حساب",
  "Disable my account": "غیرفعال کردن حساب من",
  "Single use · 24h ·": "یک‌بارمصرف · ۲۴ ساعت ·",
  "Share through an independently trusted channel.":
    "از طریق کانالی مستقل و مورد اعتماد به اشتراک بگذارید.",
  ID: "شناسه",
  Member: "عضو",
  "Community admin": "مدیر جامعه",
  "Service controls": "کنترل‌های سرویس",
  "Maintenance banner": "پیام نگهداری",
  "Save maintenance banner": "ذخیرهٔ پیام نگهداری",
  "Independently verified standby IP URL":
    "نشانی IP سرور پشتیبان با تأیید مستقل",
  "A different origin has separate browser keys. Prepare and verify a trusted device before switching endpoints. Use only an independently verified server address.":
    "مبدأ متفاوت کلیدهای مرورگر جداگانه دارد. پیش از تغییر نشانی، دستگاه مورد اعتماد را آماده و تأیید کنید. فقط از نشانی سرور با تأیید مستقل استفاده کنید.",
  "Open verified endpoint": "باز کردن نشانی تأییدشده",
  "Use only an independently verified IP endpoint. Public IP certificates expire and need renewal. A private root must be independently verified and installed before connecting; iOS also requires explicit full trust. An invalid certificate blocks the whole page, so this page cannot diagnose it reliably. Keep your verified connection instructions.":
    "فقط از نشانی IP با تأیید مستقل استفاده کنید. گواهی‌های عمومی IP منقضی می‌شوند و نیاز به تمدید دارند. ریشهٔ خصوصی باید پیش از اتصال به‌طور مستقل تأیید و نصب شود؛ در iOS اعتماد کامل نیز باید صریحاً فعال شود. گواهی نامعتبر کل صفحه را مسدود می‌کند و این صفحه نمی‌تواند آن را دقیق تشخیص دهد. راهنمای اتصال چاپ‌شده همراه داشته باشید.",
  "There is no remote delivery without a working network route. A compromised device or application origin can disclose messages. Administration cannot recover lost E2EE keys. Standby promotion requires fencing and a separately trusted origin; do not switch to an address sent by an unverified party.":
    "بدون مسیر شبکهٔ فعال، تحویل از راه دور ممکن نیست. دستگاه یا مبدأ برنامهٔ آلوده می‌تواند پیام‌ها را افشا کند. مدیر نمی‌تواند کلیدهای سرتاسری گم‌شده را بازیابی کند. فعال‌سازی سرور پشتیبان نیاز به قطع قطعی سرور قبلی و مبدأ مورد اعتماد جداگانه دارد؛ به نشانی ارسالی فرد تأییدنشده منتقل نشوید.",
  "Recover an account using an offline recovery kit":
    "بازیابی حساب با بستهٔ بازیابی آفلاین",
  "Use a separate browser profile. Recovery revokes every old device and pauses affected groups. Saved history is restored locally; contacts must independently verify and add your fresh device. Account passwords cannot recover message keys.":
    "از نمایهٔ مرورگر جداگانه استفاده کنید. بازیابی همهٔ دستگاه‌های قبلی را لغو و گروه‌های مربوط را متوقف می‌کند. تاریخچه به‌صورت محلی بازمی‌گردد؛ مخاطبان باید دستگاه تازه را مستقل تأیید و اضافه کنند. گذرواژهٔ حساب، کلیدهای پیام را بازیابی نمی‌کند.",
  "Encrypted recovery kit": "بستهٔ بازیابی رمزگذاری‌شده",
  "Separate recovery key": "کلید بازیابی جداگانه",
  "New account password": "گذرواژهٔ جدید حساب",
  "New device unlock secret": "عبارت عبور دستگاه جدید",
  "Reset account security and recover saved history":
    "بازنشانی امنیت حساب و بازیابی تاریخچهٔ ذخیره‌شده",
  "History-only kit: account recovery remains with the original recovery kit.":
    "این بسته فقط تاریخچه را دارد؛ بازیابی حساب همچنان به بستهٔ اصلی نیاز دارد.",
  "Saved history imported locally. Live device keys and pending messages were preserved.":
    "تاریخچه به‌صورت محلی وارد شد. کلیدهای فعال دستگاه و پیام‌های معلق حفظ شدند.",
  "Account security reset completed. All old devices are revoked. Restored history is local-only; contacts must verify this fresh device and explicitly re-add it.":
    "بازنشانی امنیت حساب انجام شد. تمام دستگاه‌های قبلی لغو شدند. تاریخچهٔ بازیابی‌شده فقط محلی است؛ مخاطبان باید دستگاه تازه را تأیید و دوباره اضافه کنند.",
  "Approved device connected; a fresh key package is available.":
    "دستگاه تأییدشده متصل شد؛ بستهٔ کلید تازه آماده است.",
  queued: "در صف",
  server_accepted: "پذیرفته‌شده در سرور",
  recipient_synced: "همگام‌شده با گیرنده",
  failed: "ناموفق",
  local_only: "فقط محلی",
  encrypting: "در حال رمزگذاری",
  "Voice note unavailable or integrity check failed":
    "پیام صوتی در دسترس نیست یا بررسی اصالت آن ناموفق بود",
  CRYPTO_NOT_READY: "رمزنگاری برای این محیط تأیید نشده است",
  "Use a distinct unlock passphrase with at least 20 characters":
    "یک عبارت عبور جداگانه با دست‌کم ۲۰ نویسه انتخاب کنید",
  "Voice note exceeds 25 MiB. Record a shorter note.":
    "حجم پیام صوتی بیش از ۲۵ مگابایت است. پیام کوتاه‌تری ضبط کنید.",
  "Departure requested. An owner or moderator must complete MLS removal before writes resume.":
    "درخواست خروج ثبت شد. مالک یا مدیر گروه باید حذف MLS را پیش از ادامهٔ ارسال تکمیل کند.",
  "Current device is not a group member": "دستگاه فعلی عضو گروه نیست",
  "MLS epoch refreshed through an authenticated path update.":
    "دورهٔ MLS از طریق به‌روزرسانی معتبر مسیر کلید تازه شد.",
  "Pending membership request cancelled locally and signed group history checked. Review the roster before retrying.":
    "درخواست عضویت معلق در این دستگاه لغو و تاریخچهٔ امضاشدهٔ گروه بررسی شد. پیش از تلاش دوباره، اعضا را بازبینی کنید.",
  "Ownership transferred through a signed MLS epoch update.":
    "مالکیت با به‌روزرسانی امضاشدهٔ دورهٔ MLS منتقل شد.",
  "Moderator appointed through a signed MLS epoch update.":
    "مدیر گروه با به‌روزرسانی امضاشدهٔ دورهٔ MLS تعیین شد.",
  "Revoke this device? All affected groups pause until cryptographic rekey.":
    "این دستگاه لغو شود؟ گروه‌های مربوط تا تغییر امن کلید متوقف می‌شوند.",
  "Kit too large": "حجم بسته بیش از حد مجاز است",
  "Kit account mismatch": "بسته متعلق به این حساب نیست",
  "Export decrypted message history to this device? The downloaded file contains sensitive plaintext.":
    "تاریخچهٔ رمزگشایی‌شده در این دستگاه ذخیره شود؟ فایل دریافت‌شده شامل اطلاعات حساس خوانا است.",
  "Enter a trusted HTTPS IPv4 endpoint with no path, credentials or query.":
    "یک نشانی IPv4 معتبر با HTTPS و بدون مسیر، اطلاعات ورود یا پرس‌وجو وارد کنید.",
  "Select your encrypted recovery kit (maximum 24 MB).":
    "بستهٔ بازیابی رمزگذاری‌شدهٔ خود را انتخاب کنید؛ حداکثر ۲۴ مگابایت.",
  "Unsupported recovery kit": "این بستهٔ بازیابی پشتیبانی نمی‌شود",
  "Canonical encoding failed": "کدگذاری معیار ناموفق بود",
  "Invalid delivery signature": "امضای تحویل معتبر نیست",
  "No local vault. Enroll a fresh device or recover your account.":
    "مخزن محلی موجود نیست. دستگاه تازه ثبت کنید یا حساب را بازیابی کنید.",
  "Unsupported vault. History must be recovered into a fresh device.":
    "این مخزن پشتیبانی نمی‌شود. تاریخچه باید در دستگاهی تازه بازیابی شود.",
  "Unlock the existing vault; never overwrite active MLS state.":
    "مخزن موجود را باز کنید؛ وضعیت فعال MLS را بازنویسی نکنید.",
  "Session challenge binding failed": "بررسی اتصال چالش به نشست ناموفق بود",
  "Preserve this vault. Use a separate browser profile for recovery.":
    "این مخزن را حفظ کنید. برای بازیابی از نمایهٔ مرورگر جداگانه استفاده کنید.",
  "Recovery material or unlock secret unavailable":
    "اطلاعات بازیابی یا عبارت عبور موجود نیست",
  "Vault locked": "مخزن قفل است",
  "Vault locked during persistence; unlock the durable state before continuing":
    "مخزن هنگام ذخیره قفل شد؛ پیش از ادامه وضعیت ذخیره‌شده را دوباره باز کنید",
  "A membership transition is pending durable acceptance; retry synchronization first.":
    "تغییر عضویت در انتظار پذیرش قطعی است؛ ابتدا همگام‌سازی را دوباره امتحان کنید.",
  "Unknown pending upload": "بارگذاری معلق شناخته نشد",
  "Fingerprint does not match": "اثر انگشت مطابقت ندارد",
  "Unsupported history profile": "قالب تاریخچه پشتیبانی نمی‌شود",
  "Synchronize and verify conversation first":
    "ابتدا گفتگو را همگام و تأیید کنید",
  "Synchronize before sending": "پیش از ارسال همگام‌سازی کنید",
  "Cryptographic epoch renewal required. Ask the owner or moderator to refresh the epoch.":
    "دورهٔ رمزنگاری باید تازه شود. از مالک یا مدیر گروه بخواهید دوره را تازه کند.",
  "Pending message limit reached. Reconnect and synchronize before sending more.":
    "تعداد پیام‌های معلق به حد مجاز رسیده است. پیش از ارسال بیشتر، متصل و همگام شوید.",
  "Local history limit reached; export history before continuing":
    "حجم تاریخچهٔ محلی به حد مجاز رسیده است؛ پیش از ادامه از تاریخچه خروجی بگیرید",
  "Epoch conflict: synchronize": "دورهٔ کلید ناسازگار است؛ همگام‌سازی کنید",
  "Verified head required": "آخرین وضعیت تأییدشده لازم است",
  "Conversation member limit": "تعداد اعضای گفتگو به حد مجاز رسیده است",
  "Identity changed": "هویت تغییر کرده است",
  "Member mismatch": "عضو مطابقت ندارد",
  "Current approved membership required": "عضویت معتبر فعلی لازم است",
  "Epoch mismatch": "دورهٔ کلید مطابقت ندارد",
  "Too many unresolved membership requests. Recover through a verified fresh group.":
    "درخواست‌های عضویت حل‌نشده بیش از حد است. از طریق یک گروه تازه و تأییدشده بازیابی کنید.",
  "MLS membership differs from authenticated policy":
    "اعضای MLS با سیاست تأییدشده مطابقت ندارند",
  "Unauthorized epoch transition": "تغییر دوره مجاز نیست",
  "Invalid Add": "افزودن عضو معتبر نیست",
  "Unauthorized Remove": "حذف عضو مجاز نیست",
  "Unauthorized authority change": "تغییر اختیار مجاز نیست",
  "Missing authority target": "دستگاه مقصد تغییر اختیار موجود نیست",
  "Invalid role": "نقش معتبر نیست",
  "Unknown transition": "تغییر شناخته نشد",
  "Unexpected roster change": "تغییر غیرمنتظرهٔ اعضا",
  "Membership changed before commit acceptance. Review the updated roster and retry.":
    "عضویت پیش از پذیرش تغییر کرد. فهرست تازهٔ اعضا را بررسی و دوباره تلاش کنید.",
  "Queued message crossed a membership change. Review recipients and explicitly resend.":
    "عضویت هنگام انتظار پیام تغییر کرد. گیرندگان را بررسی و پیام را صریحاً دوباره ارسال کنید.",
  "Invalid acceptance proof": "مدرک پذیرش معتبر نیست",
  "Prepared MLS state conflicts with the live vault; stop and reconcile":
    "وضعیت آمادهٔ MLS با مخزن فعال ناسازگار است؛ متوقف شوید و وضعیت را بررسی کنید",
  "Invalid signed genesis": "آغاز امضاشدهٔ گروه معتبر نیست",
  "Genesis rollback or fork detected":
    "بازگردانی یا انشعاب آغاز گروه شناسایی شد",
  "Server rollback or inconsistent retained cursor":
    "بازگردانی سرور یا نشانگر ذخیره‌شدهٔ ناسازگار",
  "Signed genesis contradicts retained history":
    "آغاز امضاشده با تاریخچهٔ ذخیره‌شده تناقض دارد",
  "Truncated proof history": "تاریخچهٔ مدارک ناقص است",
  "Delivery history gap or fork": "شکاف یا انشعاب در تاریخچهٔ تحویل",
  "Delivery hash mismatch": "هش تحویل مطابقت ندارد",
  "Commit type mismatch": "نوع تغییر عضویت مطابقت ندارد",
  "Application type mismatch": "نوع پیام برنامه مطابقت ندارد",
  "Server rollback or fork detected": "بازگردانی یا انشعاب سرور شناسایی شد",
  "Server rollback detected; synchronization paused":
    "بازگردانی سرور شناسایی شد؛ همگام‌سازی متوقف است",
  "Missing encrypted history": "بخشی از تاریخچهٔ رمزگذاری‌شده موجود نیست",
  "Envelope does not match signed history":
    "پاکت پیام با تاریخچهٔ امضاشده مطابقت ندارد",
  "Ciphertext sequence gap": "شکاف در ترتیب پیام‌های رمزگذاری‌شده",
  "Unexpected own-device message: restored or cloned state. Recover into a fresh device.":
    "پیام غیرمنتظره از دستگاه خودتان: احتمال وضعیت بازیابی‌شده یا کپی‌شده وجود دارد. در دستگاهی تازه بازیابی کنید.",
  "A cancelled transition was accepted after local state changed. Stop and recover through a verified fresh device.":
    "تغییر لغوشده پس از تغییر وضعیت محلی پذیرفته شد. متوقف شوید و با دستگاه تازه و تأییدشده بازیابی کنید.",
  "Unaccepted own commit": "تغییر عضویت این دستگاه پذیرفته نشده است",
  "Welcome mismatch": "پیام ورود گروه مطابقت ندارد",
  "MLS sender binding": "بررسی هویت فرستندهٔ MLS ناموفق بود",
  "MLS epoch or type mismatch": "نوع یا دورهٔ MLS مطابقت ندارد",
  "Hidden membership commit rejected": "تغییر پنهان عضویت رد شد",
  "Invalid authenticated event": "ساختار رویداد تأییدشده معتبر نیست",
  "Pending delivery": "تحویل در انتظار",
  "Verify device fingerprint before accepting":
    "پیش از پذیرش، اثر انگشت دستگاه را تأیید کنید",
  active: "فعال",
  rekey_required: "تغییر کلید لازم است",
  pending: "در انتظار تأیید",
  approved: "تأییدشده",
  revoked: "لغوشده",
  owner: "مالک",
  moderator: "مدیر گروه",
  member: "عضو",
  superadmin: "مدیر ارشد",
  community_admin: "مدیر جامعه",
};
export function translate(language: Language, text: string): string {
  if (language !== "fa") return text;
  if (fa[text]) return fa[text];
  for (const prefix of [
    "Pending delivery",
    "Verify device fingerprint before accepting",
  ])
    if (text.startsWith(prefix + ": "))
      return (
        fa[prefix] + ": " + translate(language, text.slice(prefix.length + 2))
      );
  return text;
}

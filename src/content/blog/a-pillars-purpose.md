---
title: A Pillar's Purpose
dek: Why your organizational security pillars deserve a second look.
date: July 22, 2026
readTime: 4 min read
tags:
- networking
- identity
images:
- src: /images/a-pillars-purpose/76e47a18a0ac431f946f1122692b6603.jpg
  alt: A picture of the Met Museum focusing on the pillars against a clear sky
sources:
- https://aws.amazon.com/what-is/mfa/
- https://www.cisecurity.org/insights/spotlight/ei-isac-cybersecurity-spotlight-principle-of-least-privilege
- https://hoop.dev/blog/how-to-prevent-lateral-movement-with-least-privilege-access
- https://www.paloaltonetworks.com/cyberpedia/what-does-a-firewall-do
- https://www.untappedcities.com/top-secrets-metropolitan-museum-of-art/
draft: false
---

Pillars in a structure are crucial to the integrity of a building. They help bear immense weight, gracefully transferring it down to the foundation. Without them, buildings could crumble, causing the loss of valuables such as history, goods, commodities, and, more importantly, people. If you look around, pillars are everywhere, keeping important structures in place and supporting the weight of thousands of people.

In this photograph, taken during a walk through Central Park, you can see one set of four pillars on the façade of the Metropolitan Museum of Art. These pillars bear an important weight, supporting the roof and helping ensure that stress does not lead to millions of dollars in damage from a collapse. Although it may seem like a lot of responsibility for just a few columns, the structure is designed with other supporting elements to help distribute the load.

This is a great metaphor for the pillars we use in security. They represent various lines of defense that help ensure a company does not collapse because of one failing point. But what do these pillars represent in security?

## Identity

One example is identity, which encompasses basic security measures used to verify who you are. The most basic and easiest way to verify identity is 2FA/MFA, also known as Multi-Factor Authentication. The purpose of MFA is to ensure that the person requesting access to an account is actually you. Anyone can guess a password, but can they guess a six-digit code sent to your phone that is visible for only 30 seconds? “[It] acts as an additional layer of security to prevent unauthorized users from accessing these accounts, even when the password has been stolen.” [1]

This is what many MFA services offer, including Microsoft Authenticator, Google Authenticator, AWS Identity, and even the authentication tool provided by your favorite app. I’ve personally used Microsoft Authenticator to access my college financial and transcript records. If you have data you want to protect, take the extra 30 seconds to secure your accounts and turn on MFA. You do not want to be the person responsible for losing your family’s pictures or the one who costs a company millions in downtime and recovery services.

## Least Privilege Access

Another action we can take to strengthen identity security in a workplace environment is least-privilege access. By “minimizing the connections between users, systems, and processes to only those needed to perform their job” [2], “It limits what attackers can see and do if they find a way into your network.” [3] With proper least-privilege access implemented, threat actors may find themselves stranded in their attempt at lateral movement.

## Networks

While we are on the topic of networks, securing your network is another metaphorical pillar. It represents the importance of monitoring, segmentation, firewalls, and more. Let’s start with firewalls. A firewall is your first line of defense, acting as a guard for your network against potential threats from the internet. By “monitor[ing] and control[ing] traffic using predefined rules… they block unauthorized access and threats.” [4] There are various forms of firewalls, including hardware, software, and cloud-based firewalls. I will not get into those details here, but feel free to learn more [here](https://www.paloaltonetworks.com/cyberpedia/types-of-firewalls). 

Next, let’s talk about segmentation. If you are driving on a road with lane markers and a car breaks down, how many lanes are affected? Likely just one. Now, imagine you are driving on a road with no lane markers. What happens to traffic? Even worse, what happens when a car breaks down? All the cars around you are affected, potentially across many lanes.

Network segmentation is a solution that uses switches and VLANs to separate your network into smaller subnetworks. Keep the accounting team in one lane, the engineering teams in another, and HR in a third lane, and so on. The benefit of segmentation is that it helps ensure threat actors cannot jump across networks. If your financial records in accounting are compromised, your employee data in HR is not automatically compromised too.

## Monitoring

Lastly, someone has to monitor your network to make sure there is no odd activity. Why would an employee be logging into a website with confidential information at 3 a.m. when their scheduled work hours are 9 a.m. to 5 p.m.? The best team to ask is your SOC (Security Operations Center) or NOC (Network Operations Center). If you do not have one because you are a small team, reaching out to an MSP to set up a budget-friendly monthly monitoring subscription could be a good idea.

## Planning Ahead

There are many more security pillars to explore, such as device management, data encryption, and backups and recovery. But for now, let’s look at what can happen when an organization’s security lacks funding. “Thirty-one pieces of sculpture were originally designed for the façade, but a lack of funds left piles of uncarved stone atop the columns.” [5] This tells the story of how 117 years passed without a sculpture being created on top of The Met’s pillars. Although the stones have become an accepted part of the façade, people began to notice this flaw and question why they were incomplete.

If you continue to let your organization operate without completing its security pillars, threat actors will find flaws in your system, causing far more damage than the unsculpted stones on top of The Met.

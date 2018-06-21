from __future__ import print_function
import argparse
import torch
import torch.utils.data
from torch import nn, optim
from torch.autograd import Variable
from torch.nn import functional as F
from torchvision.utils import save_image
import numpy as np
import pandas as pd


########## Learning parameters ##########

parser = argparse.ArgumentParser(description='GMSVAE MNIST Example')
parser.add_argument('--batch-size', type=int, default=128, metavar='N',
                    help='input batch size for training (default: 128)')
parser.add_argument('--epochs', type=int, default=100, metavar='N',
                    help='number of epochs to train (default: 10)')
parser.add_argument('--no-cuda', action='store_true', default=False,
                    help='enables CUDA training')
parser.add_argument('--seed', type=int, default=1, metavar='S',
                    help='random seed (default: 1)')
parser.add_argument('--log-interval', type=int, default=10, metavar='N',
                    help='how many batches to wait before logging training status')
# args = parser.parse_args()
args, unknown = parser.parse_known_args()
args.cuda = not args.no_cuda and torch.cuda.is_available()

torch.manual_seed(args.seed)
if args.cuda:
    torch.cuda.manual_seed(args.seed)

kwargs = {'num_workers': 1, 'pin_memory': True} if args.cuda else {}


########## Data ##########

train_loader = torch.utils.data.DataLoader(train_data,
    batch_size=args.batch_size, shuffle=True, **kwargs)

test_loader = torch.utils.data.DataLoader(test_data,
    batch_size=args.batch_size, shuffle=True, **kwargs)



########## Model ##########

class InfoCatConvVAE(nn.Module):
    def __init__(self, in_dim, num_class, sub_dim, z_dim, h_dim):
        super(InfoCatConvVAE, self).__init__()

        self.in_dim = in_dim
        self.num_class = num_class
        self.sub_dim = sub_dim
        self.z_dim = z_dim
        self.h_dim = h_dim

        self.conv1 = nn.Conv2d(1, 32, kernel_size=4, stride=2, padding=3)
        self.conv2 = nn.Conv2d(32, 32, kernel_size=4, stride=2, padding=3)
        self.conv3 = nn.Conv2d(32, 64, kernel_size=4, stride=2, padding=3)
        self.conv4 = nn.Conv2d(64, 64, kernel_size=4, stride=2, padding=3)
        self.fc1 = nn.Linear(64*5*5, h_dim)

        self.fc20 = nn.Linear(self.h_dim, self.num_class)
        self.fc21 = nn.Linear(self.h_dim + self.num_class, self.z_dim)
        self.fc22 = nn.Linear(self.h_dim + self.num_class, self.z_dim)

        self.fc3 = nn.Linear(self.z_dim, h_dim)
        self.fc4 = nn.Linear(self.h_dim, 28*28*32)

        self.deconv1 = nn.ConvTranspose2d(32, 64, kernel_size=3, stride=1, padding=1)
        self.deconv2 = nn.ConvTranspose2d(64, 32, kernel_size=3, stride=1, padding=1)
        self.deconv3 = nn.ConvTranspose2d(32, 28, kernel_size=3, stride=1, padding=1)
        self.conv5 = nn.Conv2d(28, 1, kernel_size=3, padding=1)

        self.relu = nn.ReLU()
        self.sigmoid = nn.Sigmoid()

    def encode(self, x):
        h1 = self.relu(F.dropout(self.conv1(x), p=0.25))
        h1 = self.relu(F.dropout(self.conv2(h1), p=0.25))
        h1 = self.relu(F.dropout(self.conv3(h1), p=0.25))
        h1 = self.relu(F.dropout(self.conv4(h1), p=0.25))
        h1 = h1.view(h1.size(0), -1)
        h1 = self.fc1(h1)

        a = F.softmax(self.fc20(h1), dim=1)
        mu = self.fc21(torch.cat((h1, a), 1))
        logvar = self.fc22(torch.cat((h1, a), 1))

        idt = torch.eye(self.num_class)
        if args.cuda:
            allmu = torch.stack([self.fc21(torch.cat((h1, Variable(idt[i, :].repeat(h1.size(0), 1)).cuda()), 1))
                                 for i in range(self.num_class)])
            allvar = torch.stack([self.fc22(torch.cat((h1, Variable(idt[i, :].repeat(h1.size(0), 1)).cuda()), 1))
                                  for i in range(self.num_class)])
        else:
            allmu = torch.stack([self.fc21(torch.cat((h1, Variable(idt[i, :].repeat(h1.size(0), 1))), 1))
                                 for i in range(self.num_class)])
            allvar = torch.stack([self.fc22(torch.cat((h1, Variable(idt[i, :].repeat(h1.size(0), 1))), 1))
                                  for i in range(self.num_class)])
        return mu, logvar, a, allmu, allvar

    def reparameterize(self, mu, logvar):
        if self.training:
            std = logvar.mul(0.5).exp_()
            eps = Variable(std.data.new(std.size()).normal_())
            z = eps.mul(std).add_(mu)
            return z
        else:
            return mu

    def decode(self, z):

        h3 = self.relu(F.dropout(self.fc3(z), p=0.25))
        out = self.relu(F.dropout(self.fc4(h3), p=0.25))
        # import pdb; pdb.set_trace()
        out = out.view(out.size(0), 32, 28, 28)
        out = self.relu(self.deconv1(out))
        out = self.relu(self.deconv2(out))
        out = self.relu(self.deconv3(out))
        out = self.sigmoid(self.conv5(out))

        return out

    def forward(self, x):
        mu, logvar, a, allmu, allvar = self.encode(x)
        z = self.reparameterize(mu, logvar)
        return self.decode(z), mu, logvar, a, allmu, allvar

    def __init__(self, in_dim, num_class, sub_dim, z_dim, h_dim):
        super(InfoCatVAE, self).__init__()

        self.in_dim = in_dim
        self.num_class = num_class
        self.sub_dim = sub_dim
        self.z_dim = z_dim
        self.h_dim = h_dim

        self.fc1 = nn.Linear(in_dim, h_dim)
        self.fc21 = nn.Linear(h_dim + num_class, z_dim)
        self.fc22 = nn.Linear(h_dim + num_class, z_dim)
        self.fca = nn.Linear(h_dim, num_class)
        self.fc3 = nn.Linear(z_dim, h_dim)
        self.fc4 = nn.Linear(h_dim, in_dim)

        self.relu = nn.ReLU()
        self.sigmoid = nn.Sigmoid()

    def encode(self, x):
        h1 = F.relu(F.dropout(self.fc1(x), p=0.25))
        a = F.softmax(self.fca(h1), dim=1)
        idt = torch.eye(self.num_class)

        if args.cuda:
            allmu = torch.stack([self.fc21(torch.cat((h1, Variable(idt[i, :].repeat(h1.size(0), 1)).cuda()), 1))
                                 for i in range(self.num_class)])
            allvar = torch.stack([self.fc22(torch.cat((h1, Variable(idt[i, :].repeat(h1.size(0), 1)).cuda()), 1))
                                  for i in range(self.num_class)])
        else:
            allmu = torch.stack([self.fc21(torch.cat((h1, Variable(idt[i, :].repeat(h1.size(0), 1))), 1))
                                 for i in range(self.num_class)])
            allvar = torch.stack([self.fc22(torch.cat((h1, Variable(idt[i, :].repeat(h1.size(0), 1))), 1))
                                  for i in range(self.num_class)])

        return self.fc21(torch.cat((h1, a), 1)), self.fc22(torch.cat((h1, a), 1)), a, allmu, allvar

    def reparameterize(self, mu, logvar):
        if self.training:
            std = logvar.mul(0.5).exp_()
            eps = Variable(std.data.new(std.size()).normal_())
            z = eps.mul(std).add_(mu)
            return z
        else:
            return mu

    def decode(self, z):
        h3 = F.relu(F.dropout(self.fc3(z), p=0.25))
        return self.sigmoid(self.fc4(h3))

    def forward(self, x):
        mu, logvar, a, allmu, allvar = self.encode(x.view(-1, self.in_dim))
        z = self.reparameterize(mu, logvar)
        return self.decode(z), mu, logvar, a, allmu, allvar


model = InfoCatConvVAE(in_dim, num_class, sub_dim, z_dim, h_dim)

if args.cuda:
    model.cuda()
optimizer = optim.Adam(model.parameters(), lr=1e-3)


def KLDG(mu1, mu2, logvar):
    return -0.5 * (1 + logvar - (mu1 - mu2).pow(2) - logvar.exp())


muprior = np.zeros((z_dim, num_class))

for i in range(num_class):
    for j in range(sub_dim):
        muprior[sub_dim * i + j, i] = 2

if args.cuda:
    mupriorT = Variable(torch.from_numpy(muprior).type(torch.FloatTensor)).cuda()
else:
    mupriorT = Variable(torch.from_numpy(muprior).type(torch.FloatTensor))


# Reconstruction + KL divergence losses summed over all elements and batch

def loss_function(coef, recon_x, x, mu, logvar, a, allmu, allvar):
    BCE = F.binary_cross_entropy(recon_x.view(-1, 784), x.view(-1, 784), size_average=False)

    KLD = 0
    if args.cuda:
        for i in range(10):
            KLD += torch.sum(
                torch.t(a[:, i].repeat(model.z_dim, 1)) * KLDG(allmu[i, :, :], mupriorT[:, i].repeat(allmu.size(1), 1),
                                                               allvar[i, :, :]))
    else:
        for i in range(10):
            KLD += torch.sum(torch.t(a[:, i].repeat(model.z_dim, 1)) * KLDG(allmu[i, :, :],
                                                                            mupriorT.cpu()[:, i].repeat(allmu.size(1),
                                                                                                        1),
                                                                            allvar[i, :, :]))
    # KLD = KLDG(mu, 0, logvar)

    negH = torch.sum(a.mul(torch.log(a + 0.001)))

    return BCE + 2*negH + 2*KLD, BCE, negH, KLD


def sampling(k):
    allz = []
    if args.cuda:
        for i in range(k):
            mu = torch.FloatTensor(muprior.T)
            logvar = torch.FloatTensor(np.zeros((10, model.z_dim)))
            z = model.reparameterize(Variable(mu).cuda(), Variable(logvar).cuda())
            allz.append(z)
        sample = torch.cat(allz, dim=0)  # Variable(torch.randn(64, 20))
        sample = model.decode(sample)
    else:
        for i in range(k):
            mu = torch.FloatTensor(muprior.T)
            logvar = torch.FloatTensor(np.zeros((10, model.z_dim)))
            z = model.reparameterize(Variable(mu), Variable(logvar))
            allz.append(z)
        sample = torch.cat(allz, dim=0)  # Variable(torch.randn(64, 20))
        sample = model.decode(sample)

    return sample, Variable(torch.arange(0, 10).repeat(k).long())


def train(epoch):
    model.train()
    train_loss, train_reco_loss, train_negH, train_KLD = 0, 0, 0, 0
    class_loss = []
    for batch_idx, data in enumerate(train_loader):
        data = Variable(data)
        if args.cuda:
            data = data.cuda()
        optimizer.zero_grad()
        recon_batch, mu, logvar, a, allmu, allvar = model(data.unsqueeze(1))
        loss, la, lb, lc = loss_function(10, recon_batch, data, mu, logvar, a, allmu, allvar)

        # Adversarial learning of classes

        sample, labels = sampling(10)
        if args.cuda:
            sample = sample.cuda()
            labels = labels.cuda()

        _, _, a, _, _ = model.encode(sample)
        adv_loss = F.cross_entropy(a, labels)

        (loss + 100*adv_loss).backward()

        train_loss += loss.data[0]
        train_reco_loss += la.data[0]
        train_negH += lb.data[0]
        train_KLD += lc.data[0]

        if args.cuda:
            del sample
            del labels

            torch.cuda.empty_cache()

        class_loss.append(adv_loss.data[0])
        optimizer.step()
        _, preds = torch.max(a, 1)

    torch.cuda.empty_cache()
    print('====> Epoch: {}, Reco: {:.2f}, negH: {:.2f}, KLD: {:.2f}, Class: {:.2f}'.format(
        epoch,
        train_reco_loss / len(train_loader.dataset),
        train_negH / len(train_loader.dataset),
        train_KLD / len(train_loader.dataset),
        np.mean(class_loss)))


def test(epoch):
    global test_lost_list
    model.eval()
    test_loss = 0
    for i, data in enumerate(test_loader):
        data = Variable(data, volatile=True)
        if args.cuda:
            data = data.cuda()
        recon_batch, mu, logvar, a, allmu, allvar = model(data.unsqueeze(1))
        _, preds = torch.max(a, 1)
        loss, la, lb, lc = loss_function(10, recon_batch, data, mu, logvar, a, allmu, allvar)
        test_loss += loss.data[0]
        if i == 0:
            n = min(data.size(0), 10)
            comparison = torch.cat([data.view(data.size(0), 1, 28, 28)[:n],
                                    recon_batch.view(recon_batch.size(0), 1, 28, 28)[:n]])
            save_image(comparison.data.cpu(),
                       '../InfoCatConvVAE_reco.png', nrow=n)

    if args.cuda:
        del data
        torch.cuda.empty_cache()

    test_loss /= len(test_loader.dataset)
    print('====> Test set loss: {:.4f}'.format(test_loss))
    test_lost_list.append(test_loss)



########## Model parameters ##########

in_dim = 784
num_class = 40
sub_dim = 2
z_dim = num_class*sub_dim
h_dim = 400
lambda = 2

n_epochs = 5000



########## Learning ##########

test_class_perf = []
test_lost_list = []


for epoch in range(1, n_epochs + 1):
    train(epoch)
    test(epoch)

    if epoch % 10 == 0:
        torch.save(model.state_dict(), '../InfoCatConvVAE.pt')
        delta = np.ones((10, model.z_dim))
        allz = []
        model.train()
        sample, labels = sampling(10)
        save_image(sample.view(100, 1, 28, 28).data,
                   '../InfoCatConvVAE_sample.png', nrow=10)
        if args.cuda:
            del sample
            torch.cuda.empty_cache()







